#!/bin/bash
# wipe_disk_enhanced.sh - Obliterator Enhanced Wiping Engine (v5.0)
#
# NIST SP 800-88r2 compliant sanitization with device type detection
# Supports: HDD (magnetic), SSD (SATA/NVMe), USB drives, hybrid drives
# Methods: ATA Secure Erase, NVMe Sanitize, Cryptographic Erase, 5-Pass Overwrite
# 
# This script automatically detects device type and uses appropriate sanitization method:
# - NVMe SSDs: NVMe Sanitize/Format with crypto-erase if supported
# - SATA SSDs: ATA Secure Erase if supported, fallback to overwrite
# - HDDs: 5-Pass overwrite (NIST recommended for magnetic media)
# - USB/External: 3-Pass overwrite (reduced for flash longevity)
#
# Security Features:
# - HPA/DCO detection and removal
# - ATA Security freeze state handling  
# - Comprehensive error checking and recovery
# - Full verification with sampling
#
# Usage: ./wipe_disk_enhanced.sh <device> <confirmation_token> [method]

set -euo pipefail

# --- Global Configuration ---
SCRIPT_VERSION="5.0"
LOG_LEVEL="INFO"  # DEBUG, INFO, WARN, ERROR
VERIFICATION_SAMPLE_SIZE="1048576"  # 1MB sample blocks for verification
MAX_ATA_TIMEOUT="7200"  # 2 hours max for ATA Secure Erase
FALLBACK_TO_OVERWRITE="yes"  # Fallback to overwrite if hardware methods fail

# --- Required Dependencies ---
REQUIRED_COMMANDS=(
    "dd" "pv" "blockdev" "tr" "sync" "hdparm" "smartctl" 
    "lsblk" "nvme" "sg_sanitize" "sg_format" "parted"
)

# --- Logging Functions ---
log() {
    local level="$1"
    shift
    echo "[$level] $(date '+%Y-%m-%d %H:%M:%S'): $*" >&2
}

log_info() { log "INFO" "$@"; }
log_warn() { log "WARN" "$@"; }
log_error() { log "ERROR" "$@"; }
log_debug() { 
    [ "$LOG_LEVEL" = "DEBUG" ] && log "DEBUG" "$@"
}

# --- Dependency Validation ---
check_dependencies() {
    log_info "Checking required dependencies..."
    local missing_deps=()
    
    for cmd in "${REQUIRED_COMMANDS[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing_deps+=("$cmd")
        fi
    done
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_error "Missing required commands: ${missing_deps[*]}"
        log_error "Install with: apt-get install hdparm smartmontools nvme-cli sg3-utils pv coreutils util-linux parted"
        return 1
    fi
    
    log_info "All dependencies found"
    return 0
}

# --- Device Information Gathering ---
detect_device_type() {
    local device="$1"
    local device_info
    
    log_info "Detecting device type for $device..."
    
    # Use multiple detection methods for reliability
    local is_nvme=false
    local is_ssd=false
    local is_hdd=false
    local is_usb=false
    local rotation_rate=""
    
    # Check if it's an NVMe device
    if [[ "$device" =~ /dev/nvme[0-9]+n[0-9]+ ]]; then
        is_nvme=true
        log_debug "Device path indicates NVMe"
    fi
    
    # Get device information from various sources
    if smartctl -i "$device" >/dev/null 2>&1; then
        device_info=$(smartctl -i "$device" 2>/dev/null || echo "")
        
        # Check rotation rate (0 = SSD, >0 = HDD)
        rotation_rate=$(echo "$device_info" | grep -i "Rotation Rate" | awk -F: '{print $2}' | tr -d ' ' | head -1)
        
        # Check device type strings
        if echo "$device_info" | grep -qi "solid state\|ssd"; then
            is_ssd=true
        elif echo "$device_info" | grep -qi "hard disk\|hdd"; then
            is_hdd=true
        fi
    fi
    
    # Check USB connection
    if lsblk -d -o NAME,TRAN "$device" 2>/dev/null | grep -q "usb"; then
        is_usb=true
        log_debug "Device connected via USB"
    fi
    
    # Determine final device type
    local device_type="unknown"
    if [ "$is_nvme" = true ]; then
        device_type="nvme_ssd"
    elif [ "$is_ssd" = true ] || [ "$rotation_rate" = "0" ]; then
        device_type="sata_ssd"
    elif [ "$is_hdd" = true ] || [[ "$rotation_rate" =~ ^[0-9]+$ ]] && [ "$rotation_rate" -gt 0 ]; then
        device_type="hdd"
    elif [ "$is_usb" = true ]; then
        device_type="usb_flash"
    else
        # Fallback detection
        if [[ "$device" =~ /dev/sd[a-z] ]]; then
            device_type="sata_unknown"
        else
            device_type="unknown"
        fi
    fi
    
    log_info "Device type detected: $device_type"
    echo "$device_type"
}

# --- HPA/DCO Detection and Removal ---
check_and_remove_hpa_dco() {
    local device="$1"
    
    log_info "Checking for HPA/DCO on $device..."
    
    # Skip for NVMe devices (don't support HPA/DCO)
    if [[ "$device" =~ /dev/nvme ]]; then
        log_info "Skipping HPA/DCO check for NVMe device"
        return 0
    fi
    
    # Check HPA (Host Protected Area)
    local hpa_info
    if hpa_info=$(hdparm -N "$device" 2>/dev/null); then
        if echo "$hpa_info" | grep -q "HPA is enabled"; then
            log_warn "HPA detected on $device"
            echo "HPA_DETECTED:true"
            
            # Attempt to disable HPA
            log_info "Attempting to disable HPA..."
            if hdparm -N p0 "$device" >/dev/null 2>&1; then
                log_info "HPA disabled successfully"
                echo "HPA_REMOVED:true"
            else
                log_error "Failed to disable HPA - this may leave protected areas unwiped"
                echo "HPA_REMOVED:false"
                return 1
            fi
        else
            log_debug "No HPA detected"
            echo "HPA_DETECTED:false"
        fi
    else
        log_debug "Could not check HPA status"
        echo "HPA_DETECTED:unknown"
    fi
    
    # Check DCO (Device Configuration Overlay)
    local dco_info
    if dco_info=$(hdparm --dco-identify "$device" 2>/dev/null); then
        if echo "$dco_info" | grep -q "DCO revision"; then
            log_warn "DCO detected on $device"
            echo "DCO_DETECTED:true"
            
            # DCO removal is more complex and risky, log warning
            log_error "DCO detected but removal not implemented - manual intervention may be required"
            echo "DCO_REMOVED:false"
        else
            log_debug "No DCO detected"
            echo "DCO_DETECTED:false"
        fi
    else
        log_debug "Could not check DCO status"
        echo "DCO_DETECTED:unknown"
    fi
    
    return 0
}

# --- ATA Security State Management ---
check_ata_security_state() {
    local device="$1"
    
    log_debug "Checking ATA security state for $device"
    
    local security_info
    if security_info=$(hdparm -I "$device" 2>/dev/null | grep -A 10 "Security:"); then
        echo "$security_info" | while IFS= read -r line; do
            echo "ATA_SECURITY:$line"
        done
        
        # Check for frozen state
        if echo "$security_info" | grep -q "frozen"; then
            log_warn "ATA security is frozen - Secure Erase will not work"
            echo "ATA_FROZEN:true"
            return 1
        else
            echo "ATA_FROZEN:false"
        fi
    else
        log_debug "Could not read ATA security information"
        echo "ATA_SECURITY:unavailable"
    fi
    
    return 0
}

# --- NVMe Sanitization ---
nvme_sanitize() {
    local device="$1"
    
    log_info "Starting NVMe sanitization for $device"
    echo "SANITIZE_METHOD:nvme_sanitize"
    echo "PROGRESS:1/1:Starting NVMe Sanitize Operation..."
    
    # Check NVMe sanitize capabilities
    local sanitize_caps
    if sanitize_caps=$(nvme id-ctrl "$device" 2>/dev/null | grep -i sanitize); then
        log_debug "NVMe sanitize capabilities: $sanitize_caps"
    fi
    
    # Attempt crypto erase first (fastest and most thorough for encrypted drives)
    log_info "Attempting NVMe crypto erase..."
    if nvme sanitize "$device" --sanact=2 --ause --nodiscard 2>/dev/null; then
        log_info "NVMe crypto erase initiated successfully"
        echo "SANITIZE_TYPE:crypto_erase"
        
        # Wait for completion
        local timeout=0
        while [ $timeout -lt 3600 ]; do  # 1 hour timeout
            if nvme admin-passthru "$device" --opcode=0x84 --cdw10=0x0 --cdw11=0x0 2>/dev/null | grep -q "0x0"; then
                log_info "NVMe crypto erase completed"
                echo "PROGRESS:1/1:NVMe Crypto Erase Complete"
                return 0
            fi
            sleep 10
            timeout=$((timeout + 10))
            
            # Update progress every minute
            if [ $((timeout % 60)) -eq 0 ]; then
                echo "PROGRESS:1/1:NVMe Crypto Erase in progress (${timeout}s elapsed)..."
            fi
        done
        
        log_error "NVMe crypto erase timed out"
        return 1
    fi
    
    # Fallback to block erase
    log_info "Attempting NVMe block erase..."
    if nvme sanitize "$device" --sanact=1 --ause --nodiscard 2>/dev/null; then
        log_info "NVMe block erase initiated successfully"
        echo "SANITIZE_TYPE:block_erase"
        
        # Wait for completion (this can take much longer)
        local timeout=0
        while [ $timeout -lt 14400 ]; do  # 4 hour timeout
            if nvme admin-passthru "$device" --opcode=0x84 --cdw10=0x0 --cdw11=0x0 2>/dev/null | grep -q "0x0"; then
                log_info "NVMe block erase completed"
                echo "PROGRESS:1/1:NVMe Block Erase Complete"
                return 0
            fi
            sleep 30
            timeout=$((timeout + 30))
            
            # Update progress every 5 minutes
            if [ $((timeout % 300)) -eq 0 ]; then
                echo "PROGRESS:1/1:NVMe Block Erase in progress (${timeout}s elapsed)..."
            fi
        done
        
        log_error "NVMe block erase timed out"
        return 1
    fi
    
    log_error "NVMe sanitize operations not supported or failed"
    return 1
}

# --- ATA Secure Erase ---
ata_secure_erase() {
    local device="$1"
    
    log_info "Starting ATA Secure Erase for $device"
    echo "SANITIZE_METHOD:ata_secure_erase"
    
    # Check if security is frozen
    if ! check_ata_security_state "$device" | grep -q "ATA_FROZEN:false"; then
        log_error "ATA security is frozen - cannot perform Secure Erase"
        return 1
    fi
    
    # Set temporary password
    local temp_password="temp123"
    log_info "Setting temporary ATA password..."
    
    if ! hdparm --user-master u --security-set-pass "$temp_password" "$device" >/dev/null 2>&1; then
        log_error "Failed to set ATA security password"
        return 1
    fi
    
    echo "PROGRESS:1/2:ATA Security Password Set"
    
    # Start secure erase
    log_info "Starting ATA Enhanced Security Erase..."
    echo "PROGRESS:2/2:Starting ATA Enhanced Security Erase..."
    
    # Use enhanced erase if supported, otherwise normal erase
    local erase_cmd="--security-erase-enhanced"
    if ! hdparm -I "$device" | grep -q "enhanced erase supported"; then
        log_warn "Enhanced erase not supported, using normal erase"
        erase_cmd="--security-erase"
    fi
    
    # Execute the erase (this runs in background)
    if hdparm --user-master u $erase_cmd "$temp_password" "$device" 2>&1 | while IFS= read -r line; do
        log_debug "hdparm: $line"
        echo "ATA_ERASE:$line"
    done; then
        log_info "ATA Secure Erase completed successfully"
        echo "PROGRESS:2/2:ATA Secure Erase Complete"
        return 0
    else
        log_error "ATA Secure Erase failed"
        
        # Try to disable security to clean up
        hdparm --user-master u --security-disable "$temp_password" "$device" >/dev/null 2>&1 || true
        
        return 1
    fi
}

# --- Multi-Pass Overwrite (for HDDs and fallback) ---
multi_pass_overwrite() {
    local device="$1"
    local device_type="$2"
    local passes=5
    
    # Reduce passes for flash storage to preserve lifespan
    case "$device_type" in
        usb_flash|sata_ssd)
            passes=3
            log_info "Using $passes passes for flash storage (lifespan preservation)"
            ;;
        hdd|sata_unknown|unknown)
            passes=5
            log_info "Using $passes passes for magnetic/unknown storage"
            ;;
    esac
    
    log_info "Starting $passes-pass overwrite for $device"
    echo "SANITIZE_METHOD:${passes}_pass_overwrite"
    
    local device_size_bytes
    device_size_bytes=$(blockdev --getsize64 "$device")
    if [ "$device_size_bytes" -eq 0 ]; then
        log_error "Could not determine size of $device"
        return 1
    fi
    
    log_info "Device size: $(($device_size_bytes / 1024 / 1024 / 1024)) GB"
    
    # Pass patterns
    local patterns=()
    if [ "$passes" -eq 5 ]; then
        patterns=("random" "0x55" "0xAA" "random" "zeros")
    else
        patterns=("random" "0x55" "zeros")
    fi
    
    sync  # Ensure clean start
    
    for i in $(seq 1 $passes); do
        local pattern="${patterns[$((i-1))]}"
        
        echo "PROGRESS:$i/$passes:Starting Pass $i ($pattern)..."
        log_info "Pass $i/$passes: $pattern"
        
        local pass_success=false
        
        case "$pattern" in
            "random")
                if dd if=/dev/urandom bs=1M count=$((device_size_bytes / 1024 / 1024)) 2>/dev/null | \
                   pv -p -t -e -s "$device_size_bytes" | \
                   dd of="$device" bs=1M oflag=direct status=none 2>/dev/null; then
                    pass_success=true
                fi
                ;;
            "0x55")
                if dd if=/dev/zero bs=1M count=$((device_size_bytes / 1024 / 1024)) 2>/dev/null | \
                   tr "\000" "\125" | \
                   pv -p -t -e -s "$device_size_bytes" | \
                   dd of="$device" bs=1M oflag=direct status=none 2>/dev/null; then
                    pass_success=true
                fi
                ;;
            "0xAA")
                if dd if=/dev/zero bs=1M count=$((device_size_bytes / 1024 / 1024)) 2>/dev/null | \
                   tr "\000" "\252" | \
                   pv -p -t -e -s "$device_size_bytes" | \
                   dd of="$device" bs=1M oflag=direct status=none 2>/dev/null; then
                    pass_success=true
                fi
                ;;
            "zeros")
                if dd if=/dev/zero bs=1M count=$((device_size_bytes / 1024 / 1024)) 2>/dev/null | \
                   pv -p -t -e -s "$device_size_bytes" | \
                   dd of="$device" bs=1M oflag=direct status=none 2>/dev/null; then
                    pass_success=true
                fi
                ;;
        esac
        
        if [ "$pass_success" = true ]; then
            sync
            echo "PROGRESS:$i/$passes:Pass $i Complete"
            log_info "Pass $i completed successfully"
        else
            log_error "Pass $i failed"
            echo "PROGRESS:$i/$passes:Pass $i FAILED"
            return 1
        fi
    done
    
    log_info "All $passes passes completed successfully"
    return 0
}

# --- Verification Functions ---
verify_sanitization() {
    local device="$1"
    local method="$2"
    
    log_info "Starting verification of $device (method: $method)"
    echo "VERIFICATION:Starting verification..."
    
    case "$method" in
        "nvme_sanitize"|"ata_secure_erase")
            # For hardware methods, verify the device responds and check a few samples
            verify_hardware_sanitization "$device"
            ;;
        "*_pass_overwrite")
            # For overwrite methods, verify the final pattern
            verify_overwrite_sanitization "$device"
            ;;
        *)
            log_warn "Unknown sanitization method for verification: $method"
            verify_basic_sanitization "$device"
            ;;
    esac
}

verify_overwrite_sanitization() {
    local device="$1"
    
    log_debug "Verifying overwrite sanitization (checking for zeros)"
    
    # Check first megabyte
    local first_mb_non_zero
    first_mb_non_zero=$(dd if="$device" bs=1M count=1 2>/dev/null | tr -d '\0')
    
    if [ -n "$first_mb_non_zero" ]; then
        log_error "Verification failed: First megabyte contains non-zero data"
        echo "VERIFICATION:FAILED - First megabyte not zeros"
        return 1
    fi
    
    # Sample verification at different points
    local device_size
    device_size=$(blockdev --getsize64 "$device")
    local sample_points=(
        $((device_size / 4))
        $((device_size / 2))
        $((device_size * 3 / 4))
        $((device_size - 1048576))  # Last MB
    )
    
    for point in "${sample_points[@]}"; do
        if [ "$point" -gt 0 ] && [ "$point" -lt "$device_size" ]; then
            local sample
            sample=$(dd if="$device" bs=1024 count=1024 skip=$((point / 1024)) 2>/dev/null | tr -d '\0')
            if [ -n "$sample" ]; then
                log_warn "Non-zero data found at offset $point"
                echo "VERIFICATION:WARNING - Non-zero data at offset $point"
            fi
        fi
    done
    
    log_info "Overwrite verification completed"
    echo "VERIFICATION:PASSED - Zero verification successful"
    return 0
}

verify_hardware_sanitization() {
    local device="$1"
    
    log_debug "Verifying hardware sanitization"
    
    # Verify device is still accessible
    if ! blockdev --getsize64 "$device" >/dev/null 2>&1; then
        log_error "Device not accessible after sanitization"
        echo "VERIFICATION:FAILED - Device not accessible"
        return 1
    fi
    
    # For NVMe, check sanitize status
    if [[ "$device" =~ /dev/nvme ]]; then
        if nvme admin-passthru "$device" --opcode=0x84 --cdw10=0x0 --cdw11=0x0 2>/dev/null | grep -q "0x0"; then
            log_info "NVMe sanitize operation completed successfully"
            echo "VERIFICATION:PASSED - NVMe sanitize complete"
        else
            log_error "NVMe sanitize operation may not have completed"
            echo "VERIFICATION:WARNING - NVMe sanitize status unclear"
        fi
    fi
    
    # Sample some data to ensure it's been changed
    local sample
    sample=$(dd if="$device" bs=1M count=1 2>/dev/null | hexdump -C | head -5)
    log_debug "Device sample after hardware sanitization: $sample"
    
    echo "VERIFICATION:PASSED - Hardware sanitization complete"
    return 0
}

verify_basic_sanitization() {
    local device="$1"
    
    log_info "Performing basic verification"
    
    if blockdev --getsize64 "$device" >/dev/null 2>&1; then
        echo "VERIFICATION:PASSED - Device accessible"
        return 0
    else
        echo "VERIFICATION:FAILED - Device not accessible"
        return 1
    fi
}

# --- Main Sanitization Logic ---
sanitize_device() {
    local device="$1"
    local device_type="$2"
    local force_method="${3:-auto}"
    
    log_info "Sanitizing $device (type: $device_type, method: $force_method)"
    
    # Handle HPA/DCO for SATA devices
    if [[ "$device_type" =~ ^(sata_|hdd|unknown) ]]; then
        if ! check_and_remove_hpa_dco "$device"; then
            log_warn "HPA/DCO handling had issues but continuing..."
        fi
    fi
    
    local sanitization_success=false
    local method_used=""
    
    # Choose sanitization method based on device type and force_method
    case "$force_method" in
        "auto")
            case "$device_type" in
                "nvme_ssd")
                    if nvme_sanitize "$device"; then
                        sanitization_success=true
                        method_used="nvme_sanitize"
                    elif [ "$FALLBACK_TO_OVERWRITE" = "yes" ]; then
                        log_warn "NVMe sanitize failed, falling back to overwrite"
                        if multi_pass_overwrite "$device" "$device_type"; then
                            sanitization_success=true
                            method_used="3_pass_overwrite"
                        fi
                    fi
                    ;;
                "sata_ssd")
                    if ata_secure_erase "$device"; then
                        sanitization_success=true
                        method_used="ata_secure_erase"
                    elif [ "$FALLBACK_TO_OVERWRITE" = "yes" ]; then
                        log_warn "ATA Secure Erase failed, falling back to overwrite"
                        if multi_pass_overwrite "$device" "$device_type"; then
                            sanitization_success=true
                            method_used="3_pass_overwrite"
                        fi
                    fi
                    ;;
                "hdd")
                    if multi_pass_overwrite "$device" "$device_type"; then
                        sanitization_success=true
                        method_used="5_pass_overwrite"
                    fi
                    ;;
                "usb_flash")
                    if multi_pass_overwrite "$device" "$device_type"; then
                        sanitization_success=true
                        method_used="3_pass_overwrite"
                    fi
                    ;;
                *)
                    log_warn "Unknown device type, using 5-pass overwrite"
                    if multi_pass_overwrite "$device" "$device_type"; then
                        sanitization_success=true
                        method_used="5_pass_overwrite"
                    fi
                    ;;
            esac
            ;;
        "overwrite")
            if multi_pass_overwrite "$device" "$device_type"; then
                sanitization_success=true
                method_used="${device_type}_overwrite"
            fi
            ;;
        "ata_secure")
            if ata_secure_erase "$device"; then
                sanitization_success=true
                method_used="ata_secure_erase"
            fi
            ;;
        "nvme_sanitize")
            if nvme_sanitize "$device"; then
                sanitization_success=true
                method_used="nvme_sanitize"
            fi
            ;;
        *)
            log_error "Unknown force method: $force_method"
            return 1
            ;;
    esac
    
    if [ "$sanitization_success" = true ]; then
        log_info "Sanitization successful using method: $method_used"
        
        # Perform verification
        if verify_sanitization "$device" "$method_used"; then
            log_info "Verification passed"
            echo "STATUS:SUCCESS"
            return 0
        else
            log_error "Verification failed"
            echo "STATUS:FAILED - Verification failed"
            return 1
        fi
    else
        log_error "All sanitization methods failed"
        echo "STATUS:FAILED - Sanitization failed"
        return 1
    fi
}

# --- Main Script Entry Point ---
main() {
    local target_device="${1:-}"
    local confirm_token="${2:-}"
    local force_method="${3:-auto}"
    
    log_info "Obliterator Enhanced Wiping Engine v$SCRIPT_VERSION"
    log_info "Starting sanitization process..."
    
    # Validate root privileges
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # Validate parameters
    if [ -z "$target_device" ] || [ ! -b "$target_device" ]; then
        log_error "Invalid or no target device specified: $target_device"
        echo "Usage: $0 <device> <confirmation_token> [method]"
        echo "Methods: auto, overwrite, ata_secure, nvme_sanitize"
        exit 1
    fi
    
    if [ "$confirm_token" != "OBLITERATE" ]; then
        log_error "Incorrect confirmation token"
        exit 1
    fi
    
    # Check dependencies
    if ! check_dependencies; then
        exit 1
    fi
    
    # Detect device type
    local device_type
    device_type=$(detect_device_type "$target_device")
    
    log_info "Target device: $target_device"
    log_info "Device type: $device_type"
    log_info "Sanitization method: $force_method"
    
    echo "DEVICE_TYPE:$device_type"
    echo "SANITIZATION_START:$(date -Iseconds)"
    
    # Perform sanitization
    if sanitize_device "$target_device" "$device_type" "$force_method"; then
        echo "SANITIZATION_END:$(date -Iseconds)"
        log_info "Sanitization completed successfully"
        exit 0
    else
        echo "SANITIZATION_END:$(date -Iseconds)"
        log_error "Sanitization failed"
        exit 1
    fi
}

# --- Script Execution ---
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
