#!/usr/bin/env bash
set -euo pipefail

# SuperAgente IA Pro — Staging Deployment Script
# Usage: ./deploy/deploy-staging.sh [--build] [--seed]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[DEPLOY]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# --- Pre-flight checks ---
if [ ! -f .env ]; then
    err ".env file not found. Copy deploy/staging.env.example to .env and fill in values."
    exit 1
fi

if grep -q "CHANGE_ME" .env; then
    err ".env contains placeholder values (CHANGE_ME). Update all secrets before deploying."
    exit 1
fi

if ! command -v docker &>/dev/null; then
    err "Docker is not installed or not in PATH."
    exit 1
fi

if ! docker compose version &>/dev/null && ! docker-compose version &>/dev/null; then
    err "Docker Compose is not available."
    exit 1
fi

COMPOSE_CMD="docker compose"
if ! docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
fi

BUILD_FLAG=""
SEED_FLAG=false

for arg in "$@"; do
    case $arg in
        --build) BUILD_FLAG="--build" ;;
        --seed) SEED_FLAG=true ;;
    esac
done

# --- Deploy ---
log "Starting SuperAgente IA Pro staging deployment..."

log "Pulling latest images..."
$COMPOSE_CMD pull postgres redis prometheus grafana nginx 2>/dev/null || true

if [ -n "$BUILD_FLAG" ]; then
    log "Building application images..."
    $COMPOSE_CMD build --parallel
fi

log "Starting infrastructure (PostgreSQL, Redis)..."
$COMPOSE_CMD up -d postgres redis
sleep 5

log "Waiting for PostgreSQL health check..."
for i in $(seq 1 30); do
    if $COMPOSE_CMD exec postgres pg_isready -U superagente -q 2>/dev/null; then
        log "PostgreSQL is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        err "PostgreSQL did not become ready in time."
        exit 1
    fi
    sleep 2
done

log "Starting application services..."
$COMPOSE_CMD up -d app gateway worker

log "Starting monitoring stack..."
$COMPOSE_CMD up -d monitoring prometheus grafana

log "Starting reverse proxy..."
$COMPOSE_CMD up -d nginx

log "Verifying services..."
sleep 5

SERVICES=("app" "gateway" "postgres" "redis" "nginx")
ALL_OK=true
for svc in "${SERVICES[@]}"; do
    if $COMPOSE_CMD ps "$svc" 2>/dev/null | grep -q "Up\|running"; then
        log "  ✅ $svc is running"
    else
        warn "  ❌ $svc may not be running — check logs with: docker compose logs $svc"
        ALL_OK=false
    fi
done

echo ""
if [ "$ALL_OK" = true ]; then
    log "========================================="
    log " ✅ Staging deployment complete!"
    log "========================================="
    log ""
    log " App:        http://localhost:8501"
    log " Gateway:    http://localhost:80/api/v1/health"
    log " Prometheus: http://localhost:9090"
    log " Grafana:    http://localhost:3000"
    log ""
    log " Run load tests: locust -f tests/load/locustfile.py --host=http://localhost"
else
    warn "========================================="
    warn " ⚠️  Some services may have issues."
    warn " Check: $COMPOSE_CMD logs --tail=50"
    warn "========================================="
fi
