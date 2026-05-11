#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/verify-image.sh [image_ref]
# Example: ./scripts/verify-image.sh ghcr.io/user/repo@sha256:abc123...

IMAGE="${1:-}"
if [ -z "$IMAGE" ]; then
    echo "Usage: $0 <image-reference>"
    echo "  e.g. $0 ghcr.io/owner/repo@sha256:abcdef..."
    exit 1
fi

CERT_IDENTITY_REGEX="${CERT_IDENTITY_REGEX:-https://github.com/.*/.github/workflows/.*}"
CERT_OIDC_ISSUER="${CERT_OIDC_ISSUER:-https://token.actions.githubusercontent.com}"

echo "=== SuperAgente IA — Image Verification ==="
echo "Image: ${IMAGE}"
echo ""

if ! command -v cosign &>/dev/null; then
    echo "ERROR: cosign is not installed. Install from https://docs.sigstore.dev/cosign/system_config/installation/"
    exit 1
fi

PASS=0
FAIL=0

# --- 1. Verify Cosign signature (keyless / Fulcio + Rekor) ---
echo "[1/3] Verifying Cosign keyless signature ..."
if cosign verify \
    --certificate-identity-regexp "$CERT_IDENTITY_REGEX" \
    --certificate-oidc-issuer "$CERT_OIDC_ISSUER" \
    "$IMAGE" 2>&1; then
    echo "  -> Signature: VERIFIED"
    ((PASS++))
else
    echo "  -> Signature: FAILED"
    ((FAIL++))
fi
echo ""

# --- 2. Verify SBOM attestation ---
echo "[2/3] Verifying SBOM attestation (CycloneDX) ..."
if cosign verify-attestation \
    --certificate-identity-regexp "$CERT_IDENTITY_REGEX" \
    --certificate-oidc-issuer "$CERT_OIDC_ISSUER" \
    --type cyclonedx \
    "$IMAGE" 2>&1; then
    echo "  -> SBOM attestation: VERIFIED"
    ((PASS++))
else
    echo "  -> SBOM attestation: FAILED"
    ((FAIL++))
fi
echo ""

# --- 3. Verify build provenance (GitHub Actions attestation) ---
echo "[3/3] Verifying build provenance ..."
if command -v gh &>/dev/null; then
    if gh attestation verify "$IMAGE" 2>&1; then
        echo "  -> Provenance: VERIFIED"
        ((PASS++))
    else
        echo "  -> Provenance: FAILED (gh attestation verify)"
        ((FAIL++))
    fi
else
    echo "  -> Skipped: 'gh' CLI not installed (needed for provenance verification)"
    echo "     Install from https://cli.github.com/"
fi
echo ""

# --- Summary ---
echo "=== Verification Summary ==="
echo "  Passed: ${PASS}"
echo "  Failed: ${FAIL}"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "WARNING: One or more verifications failed. Do NOT deploy this image."
    exit 1
else
    echo "All verifications passed. Image is safe to deploy."
    exit 0
fi
