#!/bin/bash
# detect_devices.sh - Advanced Device Detection and Analysis
#
# This script provides comprehensive device detection for the Obliterator system.
# It analyzes storage devices and recommends appropriate sanitization methods
# based on NIST SP 800-88r2 guidelines.
#
# Usage: ./detect_devices.sh [--json] [--device /dev/sdX]

set -euo pipefail

# --- Configuration ---
SCRIPT_VERSION="2.0"
OUTPUT_FORMAT="human"  # human, json
SPECIFIC_DEVICE=""

# --- Parse Arguments ---
while [[ $# -gt 0 ]]; do
    case $1 in
        --json)
            OUTPUT_FORMAT="json"
            shift
            ;;
        --device)
            SPECIFIC_DEVICE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--json] [--device /dev/sdX]"
            echo "Options:"
            echo "  --json     Output in JSON format"
            echo "  --device   Analyze specific device only"
            echo "  --help     Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# --- Device Analysis Functions ---
analyze_device() {
    local device="$1"
    local info=()
    
    # Basic device info
    info[0]="$device"
    info[1]="unknown"        # device_type
    info[2]="unknown"        # manufacturer  
    info[3]="unknown"        # model
    info[4]="unknown"        # serial
    info[5]="0"              # size_bytes
    info[6]="unknown"        # interface
    info[7]="unknown"        # recommended_method
    info[8]="false"          # has_hpa
    info[9]="false"          # has_dco
    info[10]="unknown"       # ata_security_state
    info[11]="unknown"       # smart_health
    info[12]="false"         # nvme_sanitize_support
    info[13]="false"         # ata_secure_erase_support
    info[14]="0"             # estimated_time_minutes
    info[15]=""              # warnings
    
    # Skip if device doesn't exist
    if [ ! -b "$device" ]; then
        info[15]="Device not found or not a block device"
        printf "%s\n" "${info[@]}"
        return 0
    fi
    
    # Get basic device information
    local device_type="unknown"
    local interface="unknown"
    local manufacturer="unknown"
    local model="unknown" 
    local serial="unknown"
    local size_bytes=0
    
    # Determine device type and interface
    if [[ "$device" =~ /dev/nvme[0-9]+n[0-9]+ ]]; then
        device_type="nvme_ssd"
        interface="nvme"
    elif [[ "$device" =~ /dev/sd[a-z] ]]; then
        interface="sata_or_usb"
        # Further detection needed
    elif [[ "$device" =~ /dev/mmcblk[0-9]+ ]]; then
        device_type="emmc"
        interface="mmc"
    fi
    
    # Get size
    if command -v blockdev >/dev/null 2>&1; then
        size_bytes=$(blockdev --getsize64 "$device" 2>/dev/null || echo "0")
    fi
    
    # SMART analysis
    local smart_available=false
    local rotation_rate=""
    local smart_health="unknown"
    
    if command -v smartctl >/dev/null 2>&1 && smartctl -i "$device" >/dev/null 2>&1; then
        smart_available=true
        local smart_info
        smart_info=$(smartctl -i "$device" 2>/dev/null || echo "")
        
        # Extract manufacturer, model, serial
        manufacturer=$(echo "$smart_info" | grep -i "vendor:\|manufacturer:" | head -1 | cut -d: -f2 | xargs 2>/dev/null || echo "unknown")
        model=$(echo "$smart_info" | grep -i "device model:\|model number:\|model:" | head -1 | cut -d: -f2 | xargs 2>/dev/null || echo "unknown")
        serial=$(echo "$smart_info" | grep -i "serial number:" | head -1 | cut -d: -f2 | xargs 2>/dev/null || echo "unknown")
        
        # Get rotation rate for HDD/SSD detection
        rotation_rate=$(echo "$smart_info" | grep -i "rotation rate" | cut -d: -f2 | xargs | cut -d' ' -f1 2>/dev/null || echo "")
        
        # Health assessment
        if smartctl -H "$device" >/dev/null 2>&1; then
            if smartctl -H "$device" 2>/dev/null | grep -q "PASSED"; then
                smart_health="healthy"
            elif smartctl -H "$device" 2>/dev/null | grep -q "FAILED"; then
                smart_health="failing"
            fi
        fi
    fi
    
    # Refined device type detection
    if [ "$device_type" = "unknown" ] && [ "$interface" = "sata_or_usb" ]; then
        # Check if it's USB connected
        if command -v lsblk >/dev/null 2>&1; then
            local transport
            transport=$(lsblk -d -o NAME,TRAN "$device" 2>/dev/null | tail -n +2 | awk '{print $2}' || echo "")
            if [ "$transport" = "usb" ]; then
                device_type="usb_flash"
                interface="usb"
            fi
        fi
        
        # Use SMART info for SSD/HDD detection
        if [ "$device_type" = "unknown" ]; then
            if [ "$rotation_rate" = "0" ] || echo "$model" | grep -qi "ssd\|solid.state"; then
                device_type="sata_ssd"
                interface="sata"
            elif [ -n "$rotation_rate" ] && [ "$rotation_rate" != "0" ]; then
                device_type="hdd"
                interface="sata"
            else
                device_type="sata_unknown"
                interface="sata"
            fi
        fi
    fi
    
    # HPA/DCO Detection (SATA devices only)
    local has_hpa="false"
    local has_dco="false"
    local ata_security_state="unknown"
    
    if [[ "$interface" =~ sata ]] && command -v hdparm >/dev/null 2>&1; then
        # Check HPA
        if hdparm -N "$device" 2>/dev/null | grep -q "HPA is enabled"; then
            has_hpa="true"
        fi
        
        # Check DCO  
        if hdparm --dco-identify "$device" 2>/dev/null | grep -q "DCO revision"; then
            has_dco="true"
        fi
        
        # Check ATA Security
        local security_info
        if security_info=$(hdparm -I "$device" 2>/dev/null | grep -A 5 "Security:"); then
            if echo "$security_info" | grep -q "frozen"; then
                ata_security_state="frozen"
            elif echo "$security_info" | grep -q "enabled"; then
                ata_security_state="enabled"
            elif echo "$security_info" | grep -q "supported"; then
                ata_security_state="supported"
            else
                ata_security_state="not_supported"
            fi
        fi
    fi
    
    # NVMe Capabilities Detection
    local nvme_sanitize_support="false"
    if [ "$device_type" = "nvme_ssd" ] && command -v nvme >/dev/null 2>&1; then
        if nvme id-ctrl "$device" 2>/dev/null | grep -qi "sanitize"; then
            nvme_sanitize_support="true"
        fi
    fi
    
    # ATA Secure Erase Support
    local ata_secure_erase_support="false"
    if [[ "$interface" =~ sata ]] && [ "$ata_security_state" != "not_supported" ]; then
        ata_secure_erase_support="true"
    fi
    
    # Recommend sanitization method
    local recommended_method="overwrite"
    local estimated_time=60
    local warnings=""
    
    case "$device_type" in
        "nvme_ssd")
            if [ "$nvme_sanitize_support" = "true" ]; then
                recommended_method="nvme_sanitize"
                estimated_time=15
            else
                recommended_method="overwrite_3pass"
                estimated_time=180
                warnings="NVMe sanitize not supported, using overwrite"
            fi
            ;;
        "sata_ssd")
            if [ "$ata_secure_erase_support" = "true" ] && [ "$ata_security_state" != "frozen" ]; then
                recommended_method="ata_secure_erase"
                estimated_time=30
            else
                recommended_method="overwrite_3pass" 
                estimated_time=120
                if [ "$ata_security_state" = "frozen" ]; then
                    warnings="ATA security frozen, cannot use Secure Erase"
                else
                    warnings="ATA Secure Erase not available"
                fi
            fi
            ;;
        "hdd")
            recommended_method="overwrite_5pass"
            estimated_time=$((size_bytes / 1024 / 1024 / 50))  # ~50MB/s estimate
            [ "$estimated_time" -lt 60 ] && estimated_time=60
            ;;
        "usb_flash")
            recommended_method="overwrite_3pass"
            estimated_time=$((size_bytes / 1024 / 1024 / 20))  # ~20MB/s estimate  
            [ "$estimated_time" -lt 30 ] && estimated_time=30
            warnings="Flash storage - reduced passes to preserve lifespan"
            ;;
        *)
            recommended_method="overwrite_5pass"
            estimated_time=120
            warnings="Unknown device type, using conservative 5-pass overwrite"
            ;;
    esac
    
    # Add HPA/DCO warnings
    if [ "$has_hpa" = "true" ]; then
        warnings="${warnings}; HPA detected - will be removed before wiping"
    fi
    if [ "$has_dco" = "true" ]; then
        warnings="${warnings}; DCO detected - may require manual intervention"
    fi
    
    # Health warnings
    if [ "$smart_health" = "failing" ]; then
        warnings="${warnings}; SMART indicates drive is failing"
    fi
    
    # Clean up warnings
    warnings=$(echo "$warnings" | sed 's/^; //' | sed 's/;  /; /g')
    
    # Update info array
    info[1]="$device_type"
    info[2]="$manufacturer" 
    info[3]="$model"
    info[4]="$serial"
    info[5]="$size_bytes"
    info[6]="$interface"
    info[7]="$recommended_method"
    info[8]="$has_hpa"
    info[9]="$has_dco" 
    info[10]="$ata_security_state"
    info[11]="$smart_health"
    info[12]="$nvme_sanitize_support"
    info[13]="$ata_secure_erase_support"
    info[14]="$estimated_time"
    info[15]="$warnings"
    
    printf "%s\n" "${info[@]}"
}

# --- JSON Output Functions ---
output_json() {
    local devices=("$@")
    
    echo "{"
    echo "  \"detection_info\": {"
    echo "    \"script_version\": \"$SCRIPT_VERSION\","
    echo "    \"timestamp\": \"$(date -Iseconds)\","
    echo "    \"system\": \"$(uname -sr)\""
    echo "  },"
    echo "  \"devices\": ["
    
    local first=true
    for device_line in "${devices[@]}"; do
        if [ "$first" = false ]; then
            echo ","
        fi
        first=false
        
        IFS=$'\n' read -d '' -ra device_info <<< "$device_line" || true
        
        echo "    {"
        echo "      \"device_path\": \"${device_info[0]}\","
        echo "      \"device_type\": \"${device_info[1]}\","
        echo "      \"manufacturer\": \"${device_info[2]}\","
        echo "      \"model\": \"${device_info[3]}\","
        echo "      \"serial_number\": \"${device_info[4]}\","
        echo "      \"size_bytes\": ${device_info[5]},"
        echo "      \"size_gb\": $(echo "scale=2; ${device_info[5]} / 1000000000" | bc -l 2>/dev/null || echo "0"),"
        echo "      \"interface\": \"${device_info[6]}\","
        echo "      \"recommended_method\": \"${device_info[7]}\","
        echo "      \"has_hpa\": ${device_info[8]},"
        echo "      \"has_dco\": ${device_info[9]},"
        echo "      \"ata_security_state\": \"${device_info[10]}\","
        echo "      \"smart_health\": \"${device_info[11]}\","
        echo "      \"nvme_sanitize_support\": ${device_info[12]},"
        echo "      \"ata_secure_erase_support\": ${device_info[13]},"
        echo "      \"estimated_time_minutes\": ${device_info[14]},"
        echo "      \"warnings\": \"${device_info[15]}\""
        echo -n "    }"
    done
    
    echo ""
    echo "  ]"
    echo "}"
}

# --- Human-Readable Output Functions ---
output_human() {
    local devices=("$@")
    
    echo "=== Obliterator Device Detection Report ==="
    echo "Generated: $(date)"
    echo "System: $(uname -sr)"
    echo ""
    
    if [ ${#devices[@]} -eq 0 ]; then
        echo "No storage devices detected."
        return
    fi
    
    local device_count=1
    for device_line in "${devices[@]}"; do
        IFS=$'\n' read -d '' -ra device_info <<< "$device_line" || true
        
        echo "Device #$device_count: ${device_info[0]}"
        echo "$(printf '%*s' ${#device_info[0]} | tr ' ' '-')"
        echo "Type:              ${device_info[1]}"
        echo "Manufacturer:      ${device_info[2]}"
        echo "Model:             ${device_info[3]}"
        echo "Serial:            ${device_info[4]}"
        
        # Format size nicely
        local size_bytes=${device_info[5]}
        if [ "$size_bytes" -gt 0 ]; then
            local size_gb=$(echo "scale=2; $size_bytes / 1000000000" | bc -l 2>/dev/null || echo "0")
            echo "Size:              ${size_gb} GB (${size_bytes} bytes)"
        else
            echo "Size:              Unknown"
        fi
        
        echo "Interface:         ${device_info[6]}"
        echo "Recommended:       ${device_info[7]}"
        echo "Estimated Time:    ${device_info[14]} minutes"
        echo "HPA/DCO:           HPA=${device_info[8]}, DCO=${device_info[9]}"
        echo "ATA Security:      ${device_info[10]}"
        echo "SMART Health:      ${device_info[11]}"
        echo "NVMe Sanitize:     ${device_info[12]}"
        echo "ATA Secure Erase:  ${device_info[13]}"
        
        if [ -n "${device_info[15]}" ]; then
            echo "Warnings:          ${device_info[15]}"
        fi
        
        echo ""
        ((device_count++))
    done
    
    # Summary
    echo "=== Method Summary ==="
    local nvme_count=0 ssd_count=0 hdd_count=0 usb_count=0 unknown_count=0
    
    for device_line in "${devices[@]}"; do
        IFS=$'\n' read -d '' -ra device_info <<< "$device_line" || true
        case "${device_info[1]}" in
            nvme_ssd) ((nvme_count++)) ;;
            sata_ssd) ((ssd_count++)) ;;
            hdd) ((hdd_count++)) ;;
            usb_flash) ((usb_count++)) ;;
            *) ((unknown_count++)) ;;
        esac
    done
    
    echo "NVMe SSDs:         $nvme_count (NVMe Sanitize recommended)"
    echo "SATA SSDs:         $ssd_count (ATA Secure Erase recommended)"  
    echo "Hard Drives:       $hdd_count (5-Pass Overwrite recommended)"
    echo "USB Flash:         $usb_count (3-Pass Overwrite recommended)"
    echo "Unknown/Other:     $unknown_count (5-Pass Overwrite recommended)"
    echo ""
    echo "Total devices detected: ${#devices[@]}"
}

# --- Main Detection Logic ---
main() {
    local devices=()
    
    if [ -n "$SPECIFIC_DEVICE" ]; then
        # Analyze specific device
        local device_info
        device_info=$(analyze_device "$SPECIFIC_DEVICE")
        devices+=("$device_info")
    else
        # Detect all block devices
        local block_devices=()
        
        if command -v lsblk >/dev/null 2>&1; then
            # Use lsblk to find block devices
            while IFS= read -r line; do
                if [[ "$line" =~ ^/dev/ ]]; then
                    block_devices+=("$line")
                fi
            done < <(lsblk -d -n -o NAME 2>/dev/null | sed 's|^|/dev/|' || echo "")
        else
            # Fallback: scan /dev for common device patterns
            for pattern in /dev/sd[a-z] /dev/nvme[0-9]n[0-9] /dev/mmcblk[0-9]; do
                for device in $pattern; do
                    if [ -b "$device" ]; then
                        block_devices+=("$device")
                    fi
                done
            done
        fi
        
        # Analyze each device
        for device in "${block_devices[@]}"; do
            if [ -b "$device" ]; then
                local device_info
                device_info=$(analyze_device "$device")
                devices+=("$device_info")
            fi
        done
    fi
    
    # Output results
    if [ "$OUTPUT_FORMAT" = "json" ]; then
        output_json "${devices[@]}"
    else
        output_human "${devices[@]}"
    fi
}

# --- Script Execution ---
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
