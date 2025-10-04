#!/bin/bash
# obliterator_preflight_check.sh
# Comprehensive diagnostic tool for Obliterator GUI components

set +e  # Don't exit on errors - we want to check everything

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to print test results
print_test() {
    local status="$1"
    local message="$2"
    local detail="${3:-}"
    
    case "$status" in
        "PASS")
            echo -e "${GREEN}[✓ PASS]${NC} $message"
            ((PASS_COUNT++))
            ;;
        "FAIL")
            echo -e "${RED}[✗ FAIL]${NC} $message"
            ((FAIL_COUNT++))
            ;;
        "WARN")
            echo -e "${YELLOW}[! WARN]${NC} $message"
            ((WARN_COUNT++))
            ;;
        "INFO")
            echo -e "${BLUE}[i INFO]${NC} $message"
            ;;
    esac
    
    if [[ -n "$detail" ]]; then
        echo "         → $detail"
    fi
}

print_header() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ==============================================================================
# START DIAGNOSTICS
# ==============================================================================

clear
echo "═══════════════════════════════════════════════════════════════"
echo "       OBLITERATOR GUI - PRE-FLIGHT DIAGNOSTIC TOOL"
echo "═══════════════════════════════════════════════════════════════"
echo "Starting comprehensive system check..."
echo "Script directory: $SCRIPT_DIR"
echo ""

# ==============================================================================
# 1. SYSTEM PRIVILEGES
# ==============================================================================
print_header "1. SYSTEM PRIVILEGES"

if [[ $EUID -eq 0 ]]; then
    print_test "PASS" "Root privileges" "Running as root (UID 0)"
else
    print_test "FAIL" "Root privileges" "NOT running as root. Run with sudo!"
fi

# ==============================================================================
# 2. PYTHON ENVIRONMENT
# ==============================================================================
print_header "2. PYTHON ENVIRONMENT"

# Check Python version
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    print_test "PASS" "Python 3 installed" "$PYTHON_VERSION"
    
    # Check Python version is 3.7+
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
    if [[ $PYTHON_MINOR -ge 7 ]]; then
        print_test "PASS" "Python version adequate" "3.$PYTHON_MINOR >= 3.7"
    else
        print_test "WARN" "Python version may be old" "3.$PYTHON_MINOR (recommend 3.7+)"
    fi
else
    print_test "FAIL" "Python 3 not found" "Install python3"
fi

# Check required Python modules
REQUIRED_MODULES=("tkinter" "PIL" "customtkinter")
for module in "${REQUIRED_MODULES[@]}"; do
    if python3 -c "import $module" 2>/dev/null; then
        if [[ "$module" == "customtkinter" ]]; then
            VERSION=$(python3 -c "import customtkinter; print(customtkinter.__version__)" 2>/dev/null)
            print_test "PASS" "Python module: $module" "Version: $VERSION"
        else
            print_test "PASS" "Python module: $module" "Available"
        fi
    else
        print_test "FAIL" "Python module: $module" "Not installed. Run: pip3 install $module"
    fi
done

# Check optional Python modules
OPTIONAL_MODULES=("certificate_backend_integration" "certificate_viewer_addon")
for module in "${OPTIONAL_MODULES[@]}"; do
    # Check if module file exists in script directory
    if [[ -f "$SCRIPT_DIR/${module}.py" ]]; then
        if python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); import $module" 2>/dev/null; then
            print_test "PASS" "Optional module: $module" "Available (PDF/Viewer features enabled)"
        else
            print_test "WARN" "Optional module: $module" "File exists but import failed"
        fi
    else
        print_test "WARN" "Optional module: $module" "Not found (JSON-only mode)"
    fi
done

# ==============================================================================
# 3. SYSTEM UTILITIES
# ==============================================================================
print_header "3. SYSTEM UTILITIES"

REQUIRED_UTILS=("lsblk" "smartctl" "dmidecode" "bash")
for util in "${REQUIRED_UTILS[@]}"; do
    if command -v "$util" &> /dev/null; then
        UTIL_PATH=$(command -v "$util")
        print_test "PASS" "System utility: $util" "Found at $UTIL_PATH"
    else
        print_test "FAIL" "System utility: $util" "Not found. Install package containing $util"
    fi
done

# Check for optional utilities
OPTIONAL_UTILS=("hdparm" "nvme-cli" "sg3-utils")
for util in "${OPTIONAL_UTILS[@]}"; do
    if command -v "$util" &> /dev/null; then
        print_test "PASS" "Optional utility: $util" "Available (enhanced features)"
    else
        print_test "WARN" "Optional utility: $util" "Not found (limited features)"
    fi
done

# ==============================================================================
# 4. SCRIPT FILES
# ==============================================================================
print_header "4. REQUIRED SCRIPT FILES"

REQUIRED_SCRIPTS=(
    "obliterator_gui_integrated.py:Main GUI application"
    "wipe_disk.sh:Disk wiping script"
)

for entry in "${REQUIRED_SCRIPTS[@]}"; do
    script_name="${entry%%:*}"
    description="${entry##*:}"
    script_path="$SCRIPT_DIR/$script_name"
    
    if [[ -f "$script_path" ]]; then
        if [[ -x "$script_path" ]] || [[ "$script_name" == *.py ]]; then
            SIZE=$(du -h "$script_path" | cut -f1)
            print_test "PASS" "$description" "$script_path ($SIZE)"
        else
            print_test "WARN" "$description" "Not executable. Run: chmod +x $script_path"
        fi
    else
        print_test "FAIL" "$description" "Not found at $script_path"
    fi
done

# Check optional scripts
OPTIONAL_SCRIPTS=(
    "detect_devices.sh:Enhanced device detection"
    "generate_certificate.sh:Certificate generator"
)

for entry in "${OPTIONAL_SCRIPTS[@]}"; do
    script_name="${entry%%:*}"
    description="${entry##*:}"
    script_path="$SCRIPT_DIR/$script_name"
    
    if [[ -f "$script_path" ]]; then
        if [[ -x "$script_path" ]]; then
            print_test "PASS" "$description (optional)" "Found and executable"
        else
            print_test "WARN" "$description (optional)" "Found but not executable"
        fi
    else
        print_test "WARN" "$description (optional)" "Not found (reduced functionality)"
    fi
done

# ==============================================================================
# 5. CONFIGURATION FILES
# ==============================================================================
print_header "5. CONFIGURATION & ASSETS"

CONFIG_FILES=(
    "purple_theme.json:UI theme file"
    "logo.png:Application logo"
)

for entry in "${CONFIG_FILES[@]}"; do
    file_name="${entry%%:*}"
    description="${entry##*:}"
    file_path="$SCRIPT_DIR/$file_name"
    
    if [[ -f "$file_path" ]]; then
        SIZE=$(du -h "$file_path" | cut -f1)
        print_test "PASS" "$description" "$file_path ($SIZE)"
    else
        print_test "WARN" "$description" "Not found (will use defaults)"
    fi
done

# ==============================================================================
# 6. DIRECTORY STRUCTURE
# ==============================================================================
print_header "6. DIRECTORY STRUCTURE"

REQUIRED_DIRS=(
    "certificates:Certificate storage"
)

for entry in "${REQUIRED_DIRS[@]}"; do
    dir_name="${entry%%:*}"
    description="${entry##*:}"
    dir_path="$SCRIPT_DIR/$dir_name"
    
    if [[ -d "$dir_path" ]]; then
        PERMS=$(stat -c "%a" "$dir_path" 2>/dev/null || stat -f "%A" "$dir_path" 2>/dev/null)
        COUNT=$(ls -1 "$dir_path" 2>/dev/null | wc -l)
        print_test "PASS" "$description directory" "$dir_path (perms: $PERMS, files: $COUNT)"
    else
        print_test "WARN" "$description directory" "Not found, will be created on first run"
    fi
done

# ==============================================================================
# 7. AUTHENTICATION SYSTEM
# ==============================================================================
print_header "7. AUTHENTICATION SYSTEM"

LOGIN_DIR="$SCRIPT_DIR/../obliterator_login"
LOGIN_SCRIPT="$LOGIN_DIR/login_system.py"

if [[ -f "$LOGIN_SCRIPT" ]]; then
    print_test "PASS" "Login system" "Found at $LOGIN_SCRIPT"
    
    # Check session file
    SESSION_FILE="$LOGIN_DIR/.session_data"
    if [[ -f "$SESSION_FILE" ]]; then
        print_test "INFO" "Active session found" "User previously authenticated"
    else
        print_test "INFO" "No active session" "User will need to authenticate"
    fi
else
    print_test "WARN" "Login system" "Not found (app will run without auth)"
fi

# ==============================================================================
# 8. BACKEND CONNECTIVITY
# ==============================================================================
print_header "8. BACKEND CONNECTIVITY"

# Check network connectivity
if ping -c 1 -W 2 8.8.8.8 &> /dev/null; then
    print_test "PASS" "Network connectivity" "Internet connection available"
    
    # Check backend URL
    BACKEND_URL="https://obliterator-certificatebackend.onrender.com"
    if curl -s --max-time 5 "$BACKEND_URL/health" &> /dev/null; then
        print_test "PASS" "Backend API" "Reachable at $BACKEND_URL"
    else
        print_test "WARN" "Backend API" "Cannot reach $BACKEND_URL (PDF generation unavailable)"
    fi
    
    # Check Supabase
    SUPABASE_URL="https://ajqmxtjlxplnbofwoxtf.supabase.co"
    if curl -s --max-time 5 "$SUPABASE_URL" &> /dev/null; then
        print_test "PASS" "Supabase connection" "Reachable"
    else
        print_test "WARN" "Supabase connection" "Cannot reach (authentication may fail)"
    fi
else
    print_test "WARN" "Network connectivity" "No internet (offline features only)"
fi

# ==============================================================================
# 9. DEVICE DETECTION TEST
# ==============================================================================
print_header "9. DEVICE DETECTION TEST"

# Test lsblk JSON output
if lsblk -d --json -o NAME,MODEL,SERIAL,SIZE,TYPE &> /dev/null; then
    DEVICE_COUNT=$(lsblk -d --json -o NAME,MODEL,SERIAL,SIZE,TYPE 2>/dev/null | grep -c '"name"')
    print_test "PASS" "Device enumeration" "Found $DEVICE_COUNT block devices"
    
    # List detected devices
    print_test "INFO" "Detected devices:"
    lsblk -d -o NAME,SIZE,TYPE,MODEL | while read -r line; do
        echo "         $line"
    done
else
    print_test "FAIL" "Device enumeration" "lsblk command failed"
fi

# Test smartctl on first device
FIRST_DEVICE=$(lsblk -d -n -o NAME 2>/dev/null | head -1)
if [[ -n "$FIRST_DEVICE" ]]; then
    if smartctl -i "/dev/$FIRST_DEVICE" &> /dev/null; then
        print_test "PASS" "SMART data access" "Can read info from /dev/$FIRST_DEVICE"
    else
        print_test "WARN" "SMART data access" "Cannot read SMART data (may need elevated privileges)"
    fi
fi

# ==============================================================================
# 10. SCRIPT FUNCTIONALITY TESTS
# ==============================================================================
print_header "10. SCRIPT FUNCTIONALITY TESTS"

# Test detect_devices.sh if available
if [[ -x "$SCRIPT_DIR/detect_devices.sh" ]]; then
    if bash "$SCRIPT_DIR/detect_devices.sh" --help &> /dev/null; then
        print_test "PASS" "Device detection script" "Script executes successfully"
    else
        print_test "FAIL" "Device detection script" "Script execution failed"
    fi
fi

# Test generate_certificate.sh if available
if [[ -x "$SCRIPT_DIR/generate_certificate.sh" ]]; then
    if bash "$SCRIPT_DIR/generate_certificate.sh" --help &> /dev/null 2>&1; then
        print_test "PASS" "Certificate generation script" "Script responds to help flag"
    else
        # Try without help flag
        if bash "$SCRIPT_DIR/generate_certificate.sh" &> /dev/null; then
            print_test "PASS" "Certificate generation script" "Script is executable"
        else
            print_test "WARN" "Certificate generation script" "Script may have issues"
        fi
    fi
fi

# ==============================================================================
# 11. GUI DEPENDENCIES
# ==============================================================================
print_header "11. GUI DEPENDENCIES"

# Test if DISPLAY is set (for X11)
if [[ -n "$DISPLAY" ]]; then
    print_test "PASS" "Display environment" "DISPLAY=$DISPLAY"
else
    print_test "WARN" "Display environment" "DISPLAY not set (may not work in SSH)"
fi

# Test if running in graphical environment
if xdpyinfo &> /dev/null; then
    print_test "PASS" "X11 server" "X server is running"
elif [[ -n "$WAYLAND_DISPLAY" ]]; then
    print_test "PASS" "Wayland server" "Wayland display is running"
else
    print_test "WARN" "Graphical environment" "No GUI detected (needs X11/Wayland)"
fi

# ==============================================================================
# 12. SYNTAX CHECK
# ==============================================================================
print_header "12. SYNTAX VALIDATION"

# Check Python syntax
if python3 -m py_compile "$SCRIPT_DIR/obliterator_gui_integrated.py" 2>/dev/null; then
    print_test "PASS" "Python syntax" "No syntax errors in main GUI file"
else
    print_test "FAIL" "Python syntax" "Syntax errors found in GUI file"
fi

# Check bash scripts syntax
for script in wipe_disk.sh detect_devices.sh generate_certificate.sh; do
    if [[ -f "$SCRIPT_DIR/$script" ]]; then
        if bash -n "$SCRIPT_DIR/$script" 2>/dev/null; then
            print_test "PASS" "Bash syntax: $script" "No syntax errors"
        else
            print_test "FAIL" "Bash syntax: $script" "Syntax errors found"
        fi
    fi
done

# ==============================================================================
# SUMMARY
# ==============================================================================
print_header "DIAGNOSTIC SUMMARY"

echo ""
echo "Results:"
echo "  ${GREEN}✓ Passed:${NC}  $PASS_COUNT"
echo "  ${YELLOW}! Warnings:${NC} $WARN_COUNT"
echo "  ${RED}✗ Failed:${NC}  $FAIL_COUNT"
echo ""

if [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ ALL CRITICAL CHECKS PASSED!${NC}"
    echo -e "${GREEN}  System is ready to run Obliterator GUI${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    if [[ $WARN_COUNT -gt 0 ]]; then
        echo ""
        echo -e "${YELLOW}Note: $WARN_COUNT warning(s) detected. App will work but some features may be limited.${NC}"
    fi
    
    echo ""
    echo "To start the application, run:"
    echo "  sudo python3 $SCRIPT_DIR/obliterator_gui_integrated.py"
    
    exit 0
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}✗ CRITICAL ISSUES DETECTED!${NC}"
    echo -e "${RED}  Please fix the failed checks before running the application${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Common fixes:"
    echo "  • Install missing packages: sudo apt install smartmontools dmidecode"
    echo "  • Install Python modules: pip3 install customtkinter pillow"
    echo "  • Make scripts executable: chmod +x $SCRIPT_DIR/*.sh"
    echo "  • Run with root privileges: sudo $0"
    
    exit 1
fi
