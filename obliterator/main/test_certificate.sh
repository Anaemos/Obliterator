#!/bin/bash
# test_certificate.sh - Test script for certificate generation
#
# This script tests the certificate generation functionality by:
# 1. Creating a test private key if needed
# 2. Running certificate generation with mock data
# 3. Validating the generated certificate
# 4. Verifying the digital signature
#
# Usage: ./test_certificate.sh

set -euo pipefail

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYS_DIR="${SCRIPT_DIR}/keys"
CERT_DIR="${SCRIPT_DIR}/certificates"
PRIVATE_KEY_PATH="${KEYS_DIR}/private_key.pem"
PUBLIC_KEY_PATH="${KEYS_DIR}/public_key.pem"
CERT_GENERATOR="${SCRIPT_DIR}/generate_certificate.sh"

# Test parameters
TEST_DEVICE="/dev/sdb"
TEST_SERIAL="TEST123456789"
TEST_STATUS="Success"

echo "=== Obliterator Certificate Generation Test ==="
echo "Test Device: $TEST_DEVICE"
echo "Test Serial: $TEST_SERIAL"
echo "Test Status: $TEST_STATUS"
echo ""

# --- Step 1: Check Dependencies ---
echo "Step 1: Checking dependencies..."
missing_deps=()
for cmd in openssl jq base64; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing_deps+=("$cmd")
  fi
done

if [ ${#missing_deps[@]} -gt 0 ]; then
  echo "ERROR: Missing dependencies: ${missing_deps[*]}" >&2
  echo "Install with: apt-get install openssl jq coreutils" >&2
  exit 1
fi
echo "✓ All dependencies found"

# --- Step 2: Create Test Keys ---
echo ""
echo "Step 2: Setting up test keys..."
mkdir -p "$KEYS_DIR"

if [ ! -f "$PRIVATE_KEY_PATH" ]; then
  echo "Generating test RSA private key (4096-bit)..."
  openssl genrsa -out "$PRIVATE_KEY_PATH" 4096
  chmod 600 "$PRIVATE_KEY_PATH"
  echo "✓ Private key generated: $PRIVATE_KEY_PATH"
else
  echo "✓ Private key already exists: $PRIVATE_KEY_PATH"
fi

# Generate public key for verification
if [ ! -f "$PUBLIC_KEY_PATH" ]; then
  echo "Extracting public key..."
  openssl rsa -in "$PRIVATE_KEY_PATH" -pubout -out "$PUBLIC_KEY_PATH"
  echo "✓ Public key generated: $PUBLIC_KEY_PATH"
else
  echo "✓ Public key already exists: $PUBLIC_KEY_PATH"
fi

# --- Step 3: Test Certificate Generation ---
echo ""
echo "Step 3: Testing certificate generation..."
mkdir -p "$CERT_DIR"

if [ ! -x "$CERT_GENERATOR" ]; then
  echo "ERROR: Certificate generator not found or not executable: $CERT_GENERATOR" >&2
  echo "Make sure generate_certificate.sh exists and is executable (chmod +x)" >&2
  exit 1
fi

echo "Running certificate generator..."
if "$CERT_GENERATOR" "$TEST_DEVICE" "$TEST_SERIAL" "$TEST_STATUS"; then
  echo "✓ Certificate generation completed successfully"
else
  echo "✗ Certificate generation failed!" >&2
  exit 1
fi

# --- Step 4: Find and Validate Generated Certificate ---
echo ""
echo "Step 4: Validating generated certificate..."

# Find the most recent certificate file
CERT_FILE=$(find "$CERT_DIR" -name "wipe-*-${TEST_SERIAL}.json" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2- || echo "")

if [ -z "$CERT_FILE" ] || [ ! -f "$CERT_FILE" ]; then
  echo "✗ Certificate file not found in $CERT_DIR" >&2
  exit 1
fi

echo "✓ Found certificate: $(basename "$CERT_FILE")"

# Validate JSON structure
echo "Validating JSON structure..."
if jq . "$CERT_FILE" >/dev/null 2>&1; then
  echo "✓ Valid JSON structure"
else
  echo "✗ Invalid JSON structure!" >&2
  exit 1
fi

# --- Step 5: Verify Certificate Content ---
echo ""
echo "Step 5: Verifying certificate content..."

# Check required fields
required_fields=(
  ".certificate_payload.tool_information.name"
  ".certificate_payload.sanitization_event.status"
  ".certificate_payload.media_information.serial_number"
  ".signature.algorithm"
  ".signature.value"
)

for field in "${required_fields[@]}"; do
  if jq -e "$field" "$CERT_FILE" >/dev/null 2>&1; then
    value=$(jq -r "$field" "$CERT_FILE")
    echo "✓ $field: $value"
  else
    echo "✗ Missing required field: $field" >&2
    exit 1
  fi
done

# --- Step 6: Verify Digital Signature ---
echo ""
echo "Step 6: Verifying digital signature..."

# Extract payload and signature for verification
TEMP_PAYLOAD="/tmp/test_cert_payload_$$.json"
TEMP_SIGNATURE="/tmp/test_cert_signature_$$.bin"

# Extract certificate payload
jq -r '.certificate_payload' "$CERT_FILE" > "$TEMP_PAYLOAD"

# Extract and decode signature
jq -r '.signature.value' "$CERT_FILE" | base64 -d > "$TEMP_SIGNATURE"

# Verify signature using public key
if openssl dgst -sha256 -verify "$PUBLIC_KEY_PATH" -signature "$TEMP_SIGNATURE" "$TEMP_PAYLOAD" >/dev/null 2>&1; then
  echo "✓ Digital signature verification PASSED"
else
  echo "✗ Digital signature verification FAILED!" >&2
  SIGNATURE_VALID=false
fi

# Cleanup temp files
rm -f "$TEMP_PAYLOAD" "$TEMP_SIGNATURE"

# --- Step 7: Certificate Information Summary ---
echo ""
echo "Step 7: Certificate summary..."
echo "Certificate File: $CERT_FILE"
echo "File Size: $(stat -c%s "$CERT_FILE") bytes"
echo ""

# Extract and display key information
echo "=== Certificate Information ==="
echo "Certificate ID: $(jq -r '.certificate_payload.certificate_metadata.certificate_id' "$CERT_FILE")"
echo "Generated: $(jq -r '.certificate_payload.certificate_metadata.generated_timestamp' "$CERT_FILE")"
echo "Tool: $(jq -r '.certificate_payload.tool_information.name' "$CERT_FILE") v$(jq -r '.certificate_payload.tool_information.version' "$CERT_FILE")"
echo "Device: $(jq -r '.certificate_payload.media_information.device_path' "$CERT_FILE")"
echo "Serial: $(jq -r '.certificate_payload.media_information.serial_number' "$CERT_FILE")"
echo "Status: $(jq -r '.certificate_payload.sanitization_event.status' "$CERT_FILE")"
echo "Method: $(jq -r '.certificate_payload.tool_information.technique' "$CERT_FILE")"
echo "Passes: $(jq -r '.certificate_payload.sanitization_details.passes_performed | length' "$CERT_FILE")"
echo ""

# --- Step 8: Test Multiple Certificates ---
echo "Step 8: Testing multiple certificate generation..."
echo "Generating additional test certificates..."

for i in {2..3}; do
  test_serial="TEST${i}23456789"
  test_device="/dev/sd$(echo {c,d} | cut -d' ' -f$((i-1)))"
  
  echo "Generating certificate $i: $test_device ($test_serial)"
  if "$CERT_GENERATOR" "$test_device" "$test_serial" "$TEST_STATUS" >/dev/null 2>&1; then
    echo "✓ Certificate $i generated successfully"
  else
    echo "✗ Certificate $i generation failed" >&2
  fi
done

# Count total certificates
TOTAL_CERTS=$(find "$CERT_DIR" -name "wipe-*.json" -type f | wc -l)
echo "✓ Total certificates generated: $TOTAL_CERTS"

# --- Final Results ---
echo ""
echo "=== TEST RESULTS ==="
if [ "${SIGNATURE_VALID:-true}" = "true" ]; then
  echo "✓ ALL TESTS PASSED"
  echo "Certificate generation is working correctly!"
  echo ""
  echo "Generated certificates are stored in: $CERT_DIR"
  echo "Private key is stored in: $PRIVATE_KEY_PATH"
  echo "Public key is stored in: $PUBLIC_KEY_PATH"
  echo ""
  echo "You can now integrate certificate generation with the main application."
  exit 0
else
  echo "✗ SIGNATURE VERIFICATION FAILED"
  echo "There may be an issue with the signing process."
  exit 1
fi
