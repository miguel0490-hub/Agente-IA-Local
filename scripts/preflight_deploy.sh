#!/usr/bin/env bash
# Comprobaciones rápidas antes de desplegar (staging/producción).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== SuperAgente preflight =="

fail=0

check_env() {
  local var="$1"
  if [[ -z "${!var:-}" ]]; then
    echo "FAIL: variable de entorno requerida no definida: $var"
    fail=1
  else
    echo "OK: $var definida"
  fi
}

for v in GEMINI_API_KEY DATABASE_URL REDIS_URL; do
  check_env "$v" || true
done

echo "-- CSS estático sincronizado con theme.py --"
python scripts/generate_static_css.py
if ! git diff --quiet -- .streamlit/static/superagente.css 2>/dev/null; then
  echo "WARN: superagente.css difiere del generado; commitea tras generate_static_css.py"
fi

echo "-- Dependencias mínimas --"
grep -qE '^google-genai>=' requirements.txt || { echo "FAIL: falta google-genai en requirements.txt"; fail=1; }
grep -qE '^Markdown>=' requirements.txt || { echo "FAIL: falta Markdown en requirements.txt"; fail=1; }

echo "-- Tests unitarios (rápido) --"
python -m pytest tests/test_llm_pipeline.py tests/test_ai_functional_audit.py::TestGeminiProvider -q --tb=line -o addopts= || fail=1

if [[ "$fail" -ne 0 ]]; then
  echo "Preflight FALLÓ"
  exit 1
fi

echo "Preflight OK"
