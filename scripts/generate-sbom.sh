#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${PROJECT_ROOT}/sbom"

mkdir -p "$OUTPUT_DIR"

echo "=== SuperAgente IA — Local SBOM Generation ==="
echo ""

# --- Source SBOM from requirements.txt (CycloneDX) ---
echo "[1/2] Generating CycloneDX SBOM from requirements.txt ..."

if ! command -v cyclonedx-py &>/dev/null; then
    echo "  -> Installing cyclonedx-bom ..."
    pip install --quiet "cyclonedx-bom>=4.0.0"
fi

cyclonedx-py requirements \
    --input-file "${PROJECT_ROOT}/requirements.txt" \
    --output-format json \
    --output-file "${OUTPUT_DIR}/sbom-source-cyclonedx.json"

echo "  -> ${OUTPUT_DIR}/sbom-source-cyclonedx.json"

# --- Container SBOM using Syft ---
echo ""
echo "[2/2] Generating CycloneDX SBOM for Docker image ..."

IMAGE_NAME="${IMAGE_NAME:-superagente-ia:latest}"

if ! command -v syft &>/dev/null; then
    echo "  -> Installing Syft ..."
    curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin
fi

if ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    echo "  -> Building Docker image '${IMAGE_NAME}' ..."
    docker build -t "$IMAGE_NAME" "$PROJECT_ROOT"
fi

syft "$IMAGE_NAME" \
    --output cyclonedx-json="${OUTPUT_DIR}/sbom-container-cyclonedx.json"

echo "  -> ${OUTPUT_DIR}/sbom-container-cyclonedx.json"

echo ""
echo "=== Done. SBOMs written to ${OUTPUT_DIR}/ ==="
ls -lh "${OUTPUT_DIR}/"
