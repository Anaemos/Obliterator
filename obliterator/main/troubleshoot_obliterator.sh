#!/bin/bash
# troubleshoot_obliterator.sh - Obliterator System Diagnostic
# 
# This script checks for common issues and missing dependencies
# that could cause the enhanced GUI to fail.

set -euo pipefail

echo "=== Obliterator System Diagnostic ==="
echo "Generated: $(date)"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISSUES_FOUND=0

# --- Check Script Files ---
echo "1. Checking for required script files..."
REQUIRED_SCRIPTS=(
    "wipe_disk.sh"
    "detect_devices.sh" 
    "generate_certificate.sh"
    "verify_certificate.sh"
    "test_certificate.sh"
    "obliterator_gui.py"
)

for script in "${REQUIRED_SCRIPTS[@]}"; do
    script_path="$SCRIPT_DIR/$script"
    if [ -f "$script_path" ]; then
        if [ -x "$script_path" ]; then
            echo "  ✓ $script (exists and executable)"
        else
            echo "  ⚠️  $script (exists but not executable)"
            echo "     Fix with: chmod +x $script_path"
            ((ISSUES_FOUND++))
        fi
    else
        echo "  ❌ $script (missing)"
        ((ISSUES_FOUND++))
    fi
done

# --- Check Dependencies ---
echo ""
echo "2. Checking system dependencies..."
REQUIRED_COMMANDS=(
    "bash" "python3" "lsblk" "smartctl" "hdparm" "nvme"
    "blockdev" "pv" "dd" "tr" "sync" "openssl" "jq" "bc"
)

for cmd in "${REQUIRED_COMMANDS[@]}"; do
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "  ✓ $cmd"
    else
        echo "  ❌ $cmd (not found)"
        ((ISSUES_FOUND++))
    fi
done

# --- Check Python Dependencies ---
echo ""
echo "3. Checking Python dependencies..."
PYTHON_PACKAGES=(
    "tkinter" "customtkinter" "PIL" "subprocess" "json" 
    "datetime" "os" "threading" "time" "sys" "queue"
)

for pkg in "${PYTHON_PACKAGES[@]}"; do
    if python3 -c "import $pkg" 2>/dev/null; then
        echo "  ✓ $pkg"
    else
        echo "  ❌ $pkg (not available)"
        ((ISSUES_FOUND++))
    fi
done

# --- Check Directory Structure ---
echo ""
echo "4. Checking directory structure..."
REQUIRED_DIRS=(
    "keys"
    "certificates"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    dir_path="$SCRIPT_DIR/$dir"
    if [ -d "$dir_path" ]; then
        echo "  ✓ $dir/ (exists)"
    else
        echo "  ⚠️  $dir/ (missing)"
        echo "     Creating: mkdir -p $dir_path"
        mkdir -p "$dir_path"
    fi
done

# --- Check Permissions ---
echo ""
echo "5. Checking permissions..."
if [ "$EUID" -eq 0 ]; then
    echo "  ✓ Running as root"
else
    echo "  ⚠️  Not running as root (required for device operations)"
    echo "     Run with: sudo $0"
    ((ISSUES_FOUND++))
fi

# --- Test Basic Device Detection ---
echo ""
echo "6. Testing basic device detection..."
if lsblk -d --json -o NAME,MODEL,SERIAL,SIZE,TYPE >/dev/null 2>&1; then
    device_count=$(lsblk -d --json -o NAME,MODEL,SERIAL,SIZE,TYPE 2>/dev/null | jq '.blockdevices | length' 2>/dev/null || echo "0")
    echo "  ✓ lsblk working (found $device_count devices)"
else
    echo "  ❌ lsblk command failed"
    ((ISSUES_FOUND++))
fi

# --- Test Enhanced Detection Script ---
echo ""
echo "7. Testing enhanced detection script..."
detect_script="$SCRIPT_DIR/detect_devices.sh"
if [ -x "$detect_script" ]; then
    if timeout 10 bash "$detect_script" --json >/dev/null 2>&1; then
        echo "  ✓ detect_devices.sh working"
    else
        echo "  ❌ detect_devices.sh failed or timed out"
        echo "     Try running manually: bash $detect_script"
        ((ISSUES_FOUND++))
    fi
else
    echo "  ❌ detect_devices.sh not executable or missing"
    ((ISSUES_FOUND++))
fi

# --- Test Certificate Generation Dependencies ---
echo ""
echo "8. Testing certificate generation..."
keys_dir="$SCRIPT_DIR/keys"
private_key="$keys_dir/private_key.pem"

if [ -f "$private_key" ]; then
    if openssl rsa -in "$private_key" -check >/dev/null 2>&1; then
        echo "  ✓ Private key valid"
    else
        echo "  ❌ Private key invalid or corrupted"
        ((ISSUES_FOUND++))
    fi
else
    echo "  ⚠️  Private key missing"
    echo "     Generate with: openssl genrsa -out $private_key 4096"
    ((ISSUES_FOUND++))
fi

# --- Summary ---
echo ""
echo "=== DIAGNOSTIC SUMMARY ==="
if [ $ISSUES_FOUND -eq 0 ]; then
    echo "✅ No issues found! System should work correctly."
else
    echo "⚠️  Found $ISSUES_FOUND issue(s) that need attention."
fi

echo ""
echo "=== QUICK FIXES ==="
echo "1. Make scripts executable:"
echo "   chmod +x *.sh *.py"
echo ""
echo "2. Install missing packages (Ubuntu/Debian):"
echo "   apt-get install hdparm smartmontools nvme-cli sg3-utils pv openssl jq bc coreutils util-linux"
echo ""
echo "3. Install Python packages:"
echo "   pip3 install customtkinter pillow"
echo ""
echo "4. Generate signing keys:"
echo "   openssl genrsa -out keys/private_key.pem 4096"
echo "   openssl rsa -in keys/private_key.pem -pubout -out keys/public_key.pem"
echo ""
echo "5. Test the fixed GUI:"
echo "   sudo python3 obliterator_gui_fixed.py"

exit $ISSUES_FOUND
