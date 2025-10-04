#!/bin/bash
# verify_certificate.sh - Obliterator Certificate Verification Tool
#
# This script verifies the digital signature and content of Obliterator certificates.
# It can be used by third parties to validate wipe certificates independently.
#
# Usage: ./verify_certificate.sh <certificate.json> [public_key.pem]

set -euo pipefail

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PUBLIC_KEY="${SCRIPT_DIR}/keys/public_key.pem"

# --- Parameters ---
CERT_FILE="${1:-}"
PUBLIC_KEY="${2:-$DEFAULT_PUBLIC_KEY}"

if [ -z "$CERT_FILE" ]; then
  echo "Usage: $0 <certificate.json> [public_key.pem]" >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  $0 certificates/wipe-20241225-143022-ABC123.json" >&2
  echo "  $0 certificates/wipe-20241225-143022-ABC123.json keys/public_key.pem" >&2
  exit 1
fi

# --- Dependency Check ---
for cmd in jq openssl base64; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: Required command '$cmd' not found." >&2
    echo "Install with: apt-get install jq openssl coreutils" >&2
    exit 1
  fi
done

echo "=== Obliterator Certificate Verification ==="
echo "Certificate: $CERT_FILE"
echo "Public Key:  $PUBLIC_KEY"
echo ""

# --- Validate Input Files ---
if [ ! -f "$CERT_FILE" ]; then
  echo "ERROR: Certificate file not found: $CERT_FILE" >&2
  exit 1
fi

if [ ! -f "$PUBLIC_KEY" ]; then
  echo "ERROR: Public key file not found: $PUBLIC_KEY" >&2
  echo "Note: If you don't have the public key, you can extract it from the private key with:" >&2
  echo "  openssl rsa -in private_key.pem -pubout -out public_key.pem" >&2
  exit 1
fi

# --- Step 1: Validate JSON Structure ---
echo "Step 1: Validating JSON structure..."
if ! jq . "$CERT_FILE" >/dev/null 2>&1; then
  echo "❌ FAILED: Invalid JSON structure" >&2
  exit 1
fi
echo "✓ Valid JSON structure"

# --- Step 2: Check Required Fields ---
echo ""
echo "Step 2: Checking required certificate fields..."

required_fields=(
  ".certificate_payload"
  ".signature"
  ".certificate_payload.certificate_metadata.certificate_id"
  ".certificate_payload.tool_information.name"
  ".certificate_payload.sanitization_event.status"
  ".certificate_payload.media_information.serial_number"
  ".signature.algorithm"
  ".signature.value"
)

missing_fields=()
for field in "${required_fields[@]}"; do
  if ! jq -e "$field" "$CERT_FILE" >/dev/null 2>&1; then
    missing_fields+=("$field")
  fi
done

if [ ${#missing_fields[@]} -gt 0 ]; then
  echo "❌ FAILED: Missing required fields:" >&2
  printf "  %s\n" "${missing_fields[@]}" >&2
  exit 1
fi
echo "✓ All required fields present"

# --- Step 3: Extract Certificate Information ---
echo ""
echo "Step 3: Extracting certificate information..."

CERT_ID=$(jq -r '.certificate_payload.certificate_metadata.certificate_id' "$CERT_FILE")
TOOL_NAME=$(jq -r '.certificate_payload.tool_information.name' "$CERT_FILE")
TOOL_VERSION=$(jq -r '.certificate_payload.tool_information.version' "$CERT_FILE")
DEVICE_PATH=$(jq -r '.certificate_payload.media_information.device_path' "$CERT_FILE")
SERIAL_NUMBER=$(jq -r '.certificate_payload.media_information.serial_number' "$CERT_FILE")
WIPE_STATUS=$(jq -r '.certificate_payload.sanitization_event.status' "$CERT_FILE")
TIMESTAMP=$(jq -r '.certificate_payload.certificate_metadata.generated_timestamp' "$CERT_FILE")
SIG_ALGORITHM=$(jq -r '.signature.algorithm' "$CERT_FILE")

echo "Certificate ID:    $CERT_ID"
echo "Tool:             $TOOL_NAME v$TOOL_VERSION"
echo "Device:           $DEVICE_PATH"
echo "Serial Number:    $SERIAL_NUMBER"
echo "Wipe Status:      $WIPE_STATUS"
echo "Generated:        $TIMESTAMP"
echo "Signature Alg:    $SIG_ALGORITHM"

# --- Step 4: Validate Certificate Content ---
echo ""
echo "Step 4: Validating certificate content..."

# Check tool name
if [ "$TOOL_NAME" != "OBLITERATOR" ]; then
  echo "⚠️  WARNING: Unexpected tool name: $TOOL_NAME (expected: OBLITERATOR)"
fi

# Check wipe status
if [ "$WIPE_STATUS" != "Success" ]; then
  echo "⚠️  WARNING: Wipe status is not 'Success': $WIPE_STATUS"
fi

# Check signature algorithm
if [ "$SIG_ALGORITHM" != "RSA-SHA256" ]; then
  echo "⚠️  WARNING: Unexpected signature algorithm: $SIG_ALGORITHM (expected: RSA-SHA256)"
fi

# Validate timestamp format (ISO 8601)
if ! echo "$TIMESTAMP" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'; then
  echo "⚠️  WARNING: Invalid timestamp format: $TIMESTAMP"
fi

echo "✓ Certificate content validation complete"

# --- Step 5: Verify Digital Signature ---
echo ""
echo "Step 5: Verifying digital signature..."

# Create temporary files
TEMP_PAYLOAD="/tmp/cert_verify_payload_$.json"
TEMP_SIGNATURE="/tmp/cert_verify_signature_$.bin"

# Clean up function
cleanup() {
  rm -f "$TEMP_PAYLOAD" "$TEMP_SIGNATURE"
}
trap cleanup EXIT

# Extract certificate payload (exactly as it was signed)
jq -r '.certificate_payload' "$CERT_FILE" > "$TEMP_PAYLOAD"

# Extract and decode the signature
if ! jq -r '.signature.value' "$CERT_FILE" | base64 -d > "$TEMP_SIGNATURE" 2>/dev/null; then
  echo "❌ FAILED: Cannot decode signature (invalid base64)" >&2
  exit 1
fi

# Verify signature
echo "Verifying signature with public key..."
if openssl dgst -sha256 -verify "$PUBLIC_KEY" -signature "$TEMP_SIGNATURE" "$TEMP_PAYLOAD" >/dev/null 2>&1; then
  echo "✅ SIGNATURE VERIFICATION PASSED"
  SIGNATURE_VALID=true
else
  echo "❌ SIGNATURE VERIFICATION FAILED"
  echo "Possible causes:" >&2
  echo "  - Certificate has been tampered with" >&2
  echo "  - Wrong public key provided" >&2
  echo "  - Certificate was not properly signed" >&2
  SIGNATURE_VALID=false
fi

# --- Step 6: Additional Validation Checks ---
echo ""
echo "Step 6: Additional validation checks..."

# Check for pass details
PASS_COUNT=$(jq -r '.certificate_payload.sanitization_details.passes_performed | length' "$CERT_FILE" 2>/dev/null || echo "0")
if [ "$PASS_COUNT" -eq 5 ]; then
  echo "✓ Correct number of sanitization passes: $PASS_COUNT"
else
  echo "⚠️  WARNING: Unexpected number of passes: $PASS_COUNT (expected: 5)"
fi

# Check NIST reference
NIST_REF=$(jq -r '.certificate_payload.certificate_metadata.nist_reference' "$CERT_FILE" 2>/dev/null || echo "null")
if echo "$NIST_REF" | grep -q "NIST SP 800-88"; then
  echo "✓ NIST standard reference found: $NIST_REF"
else
  echo "⚠️  WARNING: Missing or invalid NIST reference: $NIST_REF"
fi

# Check verification status
VERIFICATION_STATUS=$(jq -r '.certificate_payload.sanitization_details.verification_status' "$CERT_FILE" 2>/dev/null || echo "null")
if [ "$VERIFICATION_STATUS" = "Passed" ]; then
  echo "✓ Sanitization verification: $VERIFICATION_STATUS"
else
  echo "⚠️  WARNING: Sanitization verification status: $VERIFICATION_STATUS"
fi

# --- Step 7: Certificate Age Check ---
echo ""
echo "Step 7: Certificate age validation..."

if command -v date >/dev/null 2>&1; then
  # Try to parse the timestamp and check age
  if CERT_EPOCH=$(date -d "$TIMESTAMP" +%s 2>/dev/null); then
    CURRENT_EPOCH=$(date +%s)
    AGE_SECONDS=$((CURRENT_EPOCH - CERT_EPOCH))
    AGE_DAYS=$((AGE_SECONDS / 86400))
    
    echo "Certificate age: $AGE_DAYS days"
    
    if [ $AGE_DAYS -gt 365 ]; then
      echo "⚠️  WARNING: Certificate is over 1 year old"
    elif [ $AGE_DAYS -gt 90 ]; then
      echo "⚠️  NOTE: Certificate is over 3 months old"
    else
      echo "✓ Certificate age is reasonable"
    fi
  else
    echo "⚠️  WARNING: Cannot parse certificate timestamp for age validation"
  fi
else
  echo "⚠️  NOTE: 'date' command not available for age validation"
fi

# --- Step 8: File Integrity Check ---
echo ""
echo "Step 8: File integrity checks..."

# Check file size (reasonable range)
FILE_SIZE=$(stat -c%s "$CERT_FILE" 2>/dev/null || echo "0")
if [ "$FILE_SIZE" -gt 100 ] && [ "$FILE_SIZE" -lt 50000 ]; then
  echo "✓ Certificate file size: $FILE_SIZE bytes (reasonable)"
else
  echo "⚠️  WARNING: Unusual certificate file size: $FILE_SIZE bytes"
fi

# Generate file hash for integrity reference
if command -v sha256sum >/dev/null 2>&1; then
  CERT_HASH=$(sha256sum "$CERT_FILE" | cut -d' ' -f1)
  echo "✓ Certificate SHA256: $CERT_HASH"
else
  echo "⚠️  NOTE: sha256sum not available for integrity hash"
fi

# --- Final Results ---
echo ""
echo "=== VERIFICATION RESULTS ==="
echo "Certificate File: $(basename "$CERT_FILE")"
echo "Certificate ID:   $CERT_ID"
echo "Device:          $DEVICE_PATH (Serial: $SERIAL_NUMBER)"
echo "Generated:       $TIMESTAMP"
echo ""

if [ "$SIGNATURE_VALID" = true ]; then
  echo "✅ CERTIFICATE IS VALID"
  echo ""
  echo "Summary:"
  echo "  ✓ JSON structure is valid"
  echo "  ✓ All required fields present"
  echo "  ✓ Digital signature verified"
  echo "  ✓ Certificate appears authentic"
  echo ""
  echo "This certificate can be trusted as proof of secure data sanitization"
  echo "performed by $TOOL_NAME v$TOOL_VERSION on $(date -d "$TIMESTAMP" '+%B %d, %Y at %H:%M UTC' 2>/dev/null || echo "$TIMESTAMP")."
  
  exit 0
else
  echo "❌ CERTIFICATE VERIFICATION FAILED"
  echo ""
  echo "Summary:"
  echo "  ✓ JSON structure is valid"
  echo "  ✓ All required fields present"
  echo "  ❌ Digital signature verification FAILED"
  echo ""
  echo "⚠️  WARNING: This certificate cannot be trusted!"
  echo "The digital signature is invalid, which means:"
  echo "  - The certificate may have been tampered with"
  echo "  - The certificate may be counterfeit"
  echo "  - The wrong public key may have been used for verification"
  echo ""
  echo "Do NOT accept this certificate as valid proof of data sanitization."
  
  exit 1
fi
