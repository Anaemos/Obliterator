#!/bin/bash
# generate_certificate.sh - Dynamic Certificate Generation Tool
# 
# This script generates a digitally signed JSON certificate for completed wipes
# All device details are dynamically fetched - no hardcoded values
#
# Usage: ./generate_certificate.sh <device_path> <serial_number> [status] [tool_name] [tool_version]

set -euo pipefail

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRIVATE_KEY_PATH="${SCRIPT_DIR}/keys/private_key.pem"
CERT_DIR="${SCRIPT_DIR}/certificates"

# --- Parameters (all can be overridden via command line) ---
DEVICE_PATH="${1:-}"
SERIAL_NUMBER="${2:-UNKNOWN_SERIAL}"
WIPE_STATUS="${3:-Success}"
TOOL_NAME="${4:-OBLITERATOR}"
TOOL_VERSION="${5:-12.0}"

# Additional parameters via environment variables
SANITIZATION_METHOD="${SANITIZATION_METHOD:-Purge}"
SANITIZATION_TECHNIQUE="${SANITIZATION_TECHNIQUE:-5-Pass Overwrite with dd}"
VERIFICATION_METHOD="${VERIFICATION_METHOD:-Zero-byte verification}"
PASSES_PERFORMED="${PASSES_PERFORMED:-5}"

# --- Dependency Check ---
for cmd in openssl jq base64 lsblk blockdev uname hostname; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: Critical command '$cmd' is not found. Cannot proceed." >&2
    exit 1
  fi
done

if [ -z "$DEVICE_PATH" ]; then
  echo "ERROR: Device path is required as first parameter." >&2
  echo "Usage: $0 <device_path> [serial_number] [status] [tool_name] [tool_version]" >&2
  exit 1
fi

# --- Validate Private Key ---
if [ ! -f "$PRIVATE_KEY_PATH" ]; then
  echo "ERROR: Private key not found at $PRIVATE_KEY_PATH" >&2
  echo "Generate with: openssl genrsa -out $PRIVATE_KEY_PATH 4096" >&2
  exit 1
fi

mkdir -p "$CERT_DIR"

# --- Generate Timestamp ---
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")
FILE_TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")

echo "--- Certificate Generator ---"
echo "Device: $DEVICE_PATH"
echo "Serial: $SERIAL_NUMBER"
echo "Status: $WIPE_STATUS"

# --- Enhanced Device Information Gathering ---
get_device_info() {
  local device="$1"
  local manufacturer="Unknown"
  local model="Unknown"
  local size_bytes=0
  local media_type="Unknown"
  local device_type="Unknown"
  local firmware_version="Unknown"
  local interface_type="Unknown"
  
  # Try multiple methods to get device information
  
  # Method 1: smartctl (most comprehensive)
  if command -v smartctl >/dev/null 2>&1; then
    if smartctl_output=$(smartctl -i "$device" 2>/dev/null); then
      manufacturer=$(echo "$smartctl_output" | grep -i "vendor:\|manufacturer:" | head -1 | cut -d: -f2 | xargs || echo "Unknown")
      model=$(echo "$smartctl_output" | grep -i "device model\|model number\|product:" | head -1 | cut -d: -f2 | xargs || echo "Unknown")
      firmware_version=$(echo "$smartctl_output" | grep -i "firmware version" | head -1 | cut -d: -f2 | xargs || echo "Unknown")
      
      # Check if it's an SSD
      if echo "$smartctl_output" | grep -qi "solid state\|ssd"; then
        device_type="SSD"
      elif echo "$smartctl_output" | grep -qi "nvme"; then
        device_type="NVMe"
      else
        device_type="HDD"
      fi
    fi
  fi
  
  # Method 2: hdparm for additional info
  if command -v hdparm >/dev/null 2>&1 && [ "$manufacturer" == "Unknown" ]; then
    if hdparm_output=$(hdparm -I "$device" 2>/dev/null); then
      local hdparm_model=$(echo "$hdparm_output" | grep "Model Number:" | cut -d: -f2 | xargs || echo "")
      [ -n "$hdparm_model" ] && model="$hdparm_model"
    fi
  fi
  
  # Method 3: lsblk for basic info
  if command -v lsblk >/dev/null 2>&1; then
    local lsblk_info=$(lsblk -dno MODEL,SIZE,TYPE,TRAN "$device" 2>/dev/null | head -1 || echo "")
    if [ -n "$lsblk_info" ]; then
      IFS=' ' read -r lsblk_model lsblk_size lsblk_type lsblk_tran <<< "$lsblk_info"
      [ "$model" == "Unknown" ] && [ -n "$lsblk_model" ] && model="$lsblk_model"
      [ -n "$lsblk_tran" ] && interface_type="$lsblk_tran"
    fi
  fi
  
  # Method 4: /sys filesystem
  local device_name=$(basename "$device")
  if [ -d "/sys/block/$device_name" ]; then
    # Try to get vendor from sysfs
    [ -f "/sys/block/$device_name/device/vendor" ] && \
      manufacturer=$(cat "/sys/block/$device_name/device/vendor" 2>/dev/null | xargs || echo "Unknown")
    
    # Try to get model from sysfs
    [ -f "/sys/block/$device_name/device/model" ] && \
      [ "$model" == "Unknown" ] && model=$(cat "/sys/block/$device_name/device/model" 2>/dev/null | xargs || echo "Unknown")
  fi
  
  # Get device size
  if command -v blockdev >/dev/null 2>&1; then
    size_bytes=$(blockdev --getsize64 "$device" 2>/dev/null || echo 0)
  elif [ -f "/sys/block/$device_name/size" ]; then
    # Size in 512-byte sectors
    local sectors=$(cat "/sys/block/$device_name/size" 2>/dev/null || echo 0)
    size_bytes=$((sectors * 512))
  fi
  
  # Determine media type based on device characteristics
  case "$device" in
    /dev/nvme*) 
      media_type="NVMe SSD"
      [ "$interface_type" == "Unknown" ] && interface_type="NVMe"
      ;;
    /dev/sd*|/dev/hd*) 
      if [ "$device_type" == "SSD" ]; then
        media_type="SATA SSD"
      elif [ "$device_type" == "HDD" ]; then
        media_type="SATA HDD"
      else
        media_type="SATA/USB Drive"
      fi
      [ "$interface_type" == "Unknown" ] && interface_type="SATA/USB"
      ;;
    /dev/mmcblk*) 
      media_type="MMC/SD Card"
      interface_type="MMC"
      ;;
    *) 
      media_type="Block Device"
      ;;
  esac
  
  echo "$manufacturer|$model|$size_bytes|$media_type|$device_type|$firmware_version|$interface_type"
}

# --- Get Host System Information ---
get_host_info() {
  local hostname=$(hostname 2>/dev/null || echo "unknown")
  local kernel=$(uname -r 2>/dev/null || echo "unknown")
  local arch=$(uname -m 2>/dev/null || echo "unknown")
  local os_info="Unknown"
  local system_manufacturer="Unknown"
  local system_model="Unknown"
  local system_serial="Unknown"
  
  # Get OS information
  if [ -f /etc/os-release ]; then
    os_info=$(grep "PRETTY_NAME" /etc/os-release | cut -d'"' -f2 || echo "Unknown")
  elif [ -f /etc/redhat-release ]; then
    os_info=$(cat /etc/redhat-release)
  elif [ -f /etc/debian_version ]; then
    os_info="Debian $(cat /etc/debian_version)"
  fi
  
  # Get system hardware info (requires dmidecode and root privileges)
  if command -v dmidecode >/dev/null 2>&1 && [ "$EUID" -eq 0 ]; then
    system_manufacturer=$(dmidecode -s system-manufacturer 2>/dev/null | head -1 || echo "Unknown")
    system_model=$(dmidecode -s system-product-name 2>/dev/null | head -1 || echo "Unknown")
    system_serial=$(dmidecode -s system-serial-number 2>/dev/null | head -1 || echo "Unknown")
  fi
  
  echo "$hostname|$kernel|$arch|$os_info|$system_manufacturer|$system_model|$system_serial"
}

# --- Gather Dynamic Information ---
echo "Gathering device information..."
DEVICE_INFO=$(get_device_info "$DEVICE_PATH")
IFS='|' read -r MANUFACTURER MODEL DEVICE_SIZE MEDIA_TYPE DEVICE_TYPE FIRMWARE_VERSION INTERFACE_TYPE <<< "$DEVICE_INFO"

echo "Gathering host information..."
HOST_INFO=$(get_host_info)
IFS='|' read -r HOSTNAME KERNEL_VERSION ARCH OS_INFO SYSTEM_MANUFACTURER SYSTEM_MODEL SYSTEM_SERIAL <<< "$HOST_INFO"

# If serial number wasn't provided or is UNKNOWN, try to get it
if [ "$SERIAL_NUMBER" == "UNKNOWN_SERIAL" ] || [ -z "$SERIAL_NUMBER" ]; then
  if command -v smartctl >/dev/null 2>&1; then
    DETECTED_SERIAL=$(smartctl -i "$DEVICE_PATH" 2>/dev/null | grep -i "serial number" | cut -d: -f2 | xargs || echo "")
    [ -n "$DETECTED_SERIAL" ] && SERIAL_NUMBER="$DETECTED_SERIAL"
  fi
fi

# --- Generate Passes JSON Array ---
generate_passes_json() {
  local passes_json="["
  local pass_count="${PASSES_PERFORMED:-5}"
  
  if [ "$pass_count" -eq 5 ]; then
    # Standard 5-pass pattern
    passes_json+='{"pass_number":1,"pattern_type":"Random","pattern_description":"Cryptographically secure random data","timestamp":"'$TIMESTAMP'"},'
    passes_json+='{"pass_number":2,"pattern_type":"Fixed","pattern_description":"0x55 (01010101 binary pattern)","timestamp":"'$TIMESTAMP'"},'
    passes_json+='{"pass_number":3,"pattern_type":"Fixed","pattern_description":"0xAA (10101010 binary pattern)","timestamp":"'$TIMESTAMP'"},'
    passes_json+='{"pass_number":4,"pattern_type":"Random","pattern_description":"Cryptographically secure random data","timestamp":"'$TIMESTAMP'"},'
    passes_json+='{"pass_number":5,"pattern_type":"Zeros","pattern_description":"0x00 (all zeros - final pass)","timestamp":"'$TIMESTAMP'"}'
  else
    # Generic pass description for other patterns
    for i in $(seq 1 $pass_count); do
      [ $i -gt 1 ] && passes_json+=","
      passes_json+='{"pass_number":'$i',"pattern_type":"Pattern","pattern_description":"Pass '$i' of '$pass_count'","timestamp":"'$TIMESTAMP'"}'
    done
  fi
  
  passes_json+="]"
  echo "$passes_json"
}

# --- Get Risk Assessment Based on Media Type ---
get_risk_assessment() {
  case "$DEVICE_TYPE" in
    "SSD"|"NVMe")
      echo "Medium - Flash media with wear leveling may retain data in unmapped blocks"
      ;;
    "HDD")
      echo "Low - Magnetic media overwrite is effective for data sanitization"
      ;;
    *)
      echo "Medium - Risk level depends on underlying storage technology"
      ;;
  esac
}

# --- Get Follow-up Recommendations ---
get_follow_up_recommendation() {
  case "$DEVICE_TYPE" in
    "SSD"|"NVMe")
      echo "Consider physical destruction or cryptographic erasure for high-security applications"
      ;;
    "HDD")
      echo "Physical destruction recommended for classified data environments"
      ;;
    *)
      echo "Verify sanitization effectiveness based on data sensitivity requirements"
      ;;
  esac
}

# --- Create Certificate (FLAT STRUCTURE - NO certificate_payload wrapper) ---
create_flat_certificate() {
cat << EOF
{
  "certificate_metadata": {
    "version": "2.0",
    "generated_timestamp": "$TIMESTAMP",
    "nist_reference": "NIST SP 800-88r2",
    "certificate_id": "$(uuidgen 2>/dev/null || echo "${FILE_TIMESTAMP}-${RANDOM}")"
  },
  "tool_information": {
    "name": "$TOOL_NAME",
    "version": "$TOOL_VERSION",
    "method": "$SANITIZATION_METHOD",
    "technique": "$SANITIZATION_TECHNIQUE",
    "verification_method": "$VERIFICATION_METHOD"
  },
  "sanitization_event": {
    "timestamp": "$TIMESTAMP",
    "status": "$WIPE_STATUS",
    "operator": {
      "system_user": "$(whoami)",
      "hostname": "$HOSTNAME",
      "timestamp": "$TIMESTAMP"
    }
  },
  "media_information": {
    "device_path": "$DEVICE_PATH",
    "manufacturer": "$MANUFACTURER",
    "model": "$MODEL",
    "serial_number": "$SERIAL_NUMBER",
    "firmware_version": "$FIRMWARE_VERSION",
    "interface_type": "$INTERFACE_TYPE",
    "media_type": "$MEDIA_TYPE",
    "device_type": "$DEVICE_TYPE",
    "capacity_bytes": $DEVICE_SIZE,
    "capacity_gb": $(echo "scale=2; $DEVICE_SIZE / 1000000000" | bc -l 2>/dev/null || echo "0"),
    "pre_sanitization_classification": "${PRE_CLASSIFICATION:-Unknown}",
    "post_sanitization_classification": "${POST_CLASSIFICATION:-Unclassified}"
  },
  "sanitization_details": {
    "passes_performed": $(generate_passes_json),
    "verification_status": "${VERIFICATION_STATUS:-Passed}",
    "verification_details": "$VERIFICATION_METHOD"
  },
  "host_system_information": {
    "hostname": "$HOSTNAME",
    "operating_system": "$OS_INFO",
    "kernel_version": "$KERNEL_VERSION",
    "architecture": "$ARCH",
    "system_manufacturer": "$SYSTEM_MANUFACTURER",
    "system_model": "$SYSTEM_MODEL",
    "system_serial": "$SYSTEM_SERIAL",
    "execution_environment": "${EXECUTION_ENV:-Bootable Live USB (Air-gapped)}",
    "tools_used": [
      "dd (GNU coreutils)",
      "pv (pipe viewer)",
      "blockdev",
      "smartctl",
      "openssl"
    ]
  },
  "compliance_information": {
    "standard": "NIST SP 800-88r2",
    "sanitization_method": "$SANITIZATION_METHOD",
    "residual_risk_assessment": "$(get_risk_assessment)",
    "recommended_follow_up": "$(get_follow_up_recommendation)"
  },
  "signature": {
    "algorithm": "RSA-SHA256",
    "format": "PKCS#1 v1.5",
    "value": "SIGNATURE_PLACEHOLDER",
    "signed_timestamp": "$TIMESTAMP"
  }
}
EOF
}

# --- Generate and Sign Certificate ---
echo "Generating certificate..."
CERT_TEMPLATE=$(create_flat_certificate)

echo "Validating JSON structure..."
echo "$CERT_TEMPLATE" | jq . > /dev/null || {
  echo "ERROR: Generated JSON is invalid!" >&2
  exit 1
}

# Create payload for signing (everything except the signature field itself)
PAYLOAD_TO_SIGN=$(echo "$CERT_TEMPLATE" | jq 'del(.signature)')

echo "Signing certificate with private key..."
SIGNATURE=$(echo -n "$PAYLOAD_TO_SIGN" | openssl dgst -sha256 -sign "$PRIVATE_KEY_PATH" | base64 -w 0)

# Insert the actual signature into the template
SIGNED_CERT=$(echo "$CERT_TEMPLATE" | jq --arg sig "$SIGNATURE" '.signature.value = $sig')

# --- Save Certificate ---
CERT_FILENAME="wipe-${FILE_TIMESTAMP}-${SERIAL_NUMBER}.json"
CERT_FILEPATH="$CERT_DIR/$CERT_FILENAME"

echo "Saving certificate to: $CERT_FILEPATH"
echo "$SIGNED_CERT" | jq . > "$CERT_FILEPATH"

if [ -f "$CERT_FILEPATH" ] && jq . "$CERT_FILEPATH" >/dev/null 2>&1; then
  echo "SUCCESS: Certificate generated and saved!"
  echo "File: $CERT_FILEPATH"
  echo "Device: $DEVICE_PATH ($MODEL)"
  echo "Serial: $SERIAL_NUMBER"
  echo "Certificate ID: $(jq -r '.certificate_metadata.certificate_id' "$CERT_FILEPATH")"
else
  echo "ERROR: Failed to create certificate file!" >&2
  exit 1
fi

exit 0
