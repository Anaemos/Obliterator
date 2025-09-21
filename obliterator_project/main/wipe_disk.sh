#!/bin/bash
# wipe_disk.sh - Obliterator Wiping Engine (v4 - 5-Pass dd)
#
# This script uses a highly reliable 5-pass `dd` method.
# It includes strict error checking and dependency validation.
#
# 5-Pass Strategy:
# 1. Random Data
# 2. Fixed Pattern (0x55)
# 3. Complementary Pattern (0xAA)
# 4. Random Data
# 5. Zeros (Final Pass)

# --- Strict Mode ---
# -e: Exit immediately if a command exits with a non-zero status.
# -u: Treat unset variables as an error.
# -o pipefail: The return value of a pipeline is the status of the last
#              command to exit with a non-zero status. CRITICAL for our dd pipes.
set -euo pipefail

# --- Dependency Check ---
# Ensure all required commands are available before starting.
for cmd in dd pv blockdev tr; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: Critical command '$cmd' is not found. Cannot proceed." >&2
    exit 1
  fi
done

# --- Parameters and Safety Checks ---
TARGET_DEVICE="${1:-}"
CONFIRM_TOKEN="${2:-}"

if [ "$EUID" -ne 0 ]; then
  echo "ERROR: This script must be run as root." >&2
  exit 1
fi

if [ -z "$TARGET_DEVICE" ] || [ ! -b "$TARGET_DEVICE" ]; then
  echo "ERROR: Invalid or no target device specified. Target must be a block device." >&2
  exit 1
fi

if [ "$CONFIRM_TOKEN" != "OBLITERATE" ]; then
  echo "ERROR: Incorrect confirmation token. Aborting for safety." >&2
  exit 1
fi

# --- Wiping Logic ---
echo "--- Starting 5-Pass Sanitization on $TARGET_DEVICE ---"
DEVICE_SIZE_BYTES=$(blockdev --getsize64 "$TARGET_DEVICE")
if [ "$DEVICE_SIZE_BYTES" -eq 0 ]; then
    echo "ERROR: Could not determine size of $TARGET_DEVICE. Aborting." >&2
    exit 1
fi

echo "WIPE_METHOD: 5-pass-dd-robust"
echo "DEVICE_SIZE: $(($DEVICE_SIZE_BYTES / 1024 / 1024 / 1024)) GB"
sync

# --- Pass 1: Random Data ---
echo "PROGRESS:1/5:Starting Pass 1 (Random Data)..."
dd if=/dev/urandom bs=1M | pv -p -t -e -s "$DEVICE_SIZE_BYTES" | dd of="$TARGET_DEVICE" bs=1M oflag=direct status=none
sync
echo "PROGRESS:1/5:Pass 1 Complete."

# --- Pass 2: Fixed Pattern (0x55) ---
echo "PROGRESS:2/5:Starting Pass 2 (Pattern 0x55)..."
dd if=/dev/zero bs=1M | tr "\000" "\125" | pv -p -t -e -s "$DEVICE_SIZE_BYTES" | dd of="$TARGET_DEVICE" bs=1M oflag=direct status=none
sync
echo "PROGRESS:2/5:Pass 2 Complete."

# --- Pass 3: Complementary Pattern (0xAA) ---
echo "PROGRESS:3/5:Starting Pass 3 (Pattern 0xAA)..."
dd if=/dev/zero bs=1M | tr "\000" "\252" | pv -p -t -e -s "$DEVICE_SIZE_BYTES" | dd of="$TARGET_DEVICE" bs=1M oflag=direct status=none
sync
echo "PROGRESS:3/5:Pass 3 Complete."

# --- Pass 4: Random Data ---
echo "PROGRESS:4/5:Starting Pass 4 (Random Data)..."
dd if=/dev/urandom bs=1M | pv -p -t -e -s "$DEVICE_SIZE_BYTES" | dd of="$TARGET_DEVICE" bs=1M oflag=direct status=none
sync
echo "PROGRESS:4/5:Pass 4 Complete."

# --- Pass 5: Zeros ---
echo "PROGRESS:5/5:Starting Pass 5 (Zeros)..."
dd if=/dev/zero bs=1M | pv -p -t -e -s "$DEVICE_SIZE_BYTES" | dd of="$TARGET_DEVICE" bs=1M oflag=direct status=none
sync
echo "PROGRESS:5/5:Pass 5 Complete."

# --- Verification Step ---
echo "VERIFICATION:Starting final verification..."
# After the final zero pass, the first megabyte of the disk should be all zeros.
FIRST_MB_NON_ZERO=$(dd if="$TARGET_DEVICE" bs=1M count=1 2>/dev/null | tr -d '\0')

if [ -n "$FIRST_MB_NON_ZERO" ]; then
    echo "VERIFICATION:FAILED - The first megabyte contains non-zero data." >&2
    exit 1 # This is a critical failure.
else
    echo "VERIFICATION:PASSED - The first megabyte is all zeros as expected."
fi

echo "--- Sanitization Complete on $TARGET_DEVICE ---"
echo "STATUS:SUCCESS"

exit 0
