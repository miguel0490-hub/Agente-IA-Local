# Kubernetes Deployment — SuperAgente IA

Production-ready Helm chart for deploying SuperAgente IA on Kubernetes with full security hardening, autoscaling, and high availability.

## Architecture

```
                    ┌──────────────┐
                    │   Ingress    │  (TLS termination, cert-manager)
                    │  (nginx)     │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
     ┌────────▼──┐  ┌──────▼──┐  ┌─────▼────────┐
     │  App (x3) │  │ Worker  │  │  Monitoring   │
     │ Streamlit │  │ (x3)   │  │  FastAPI (x2) │
     │  :8501    │  │  RQ     │  │  :8080        │
     └─────┬─────┘  └───┬────┘  └───────┬───────┘
           │             │               │
     ┌─────▼─────────────▼───────────────▼──────┐
     │          PostgreSQL  +  Redis            │
     └──────────────────────────────────────────┘
```

## Prerequisites

| Tool | Version |
|------|---------|
| Kubernetes | >= 1.25 |
| Helm | >= 3.12 |
| kubectl | >= 1.25 |
| cert-manager | >= 1.12 (for TLS) |
| NGINX Ingress Controller | >= 1.8 |
| Metrics Server | Required for HPA |

## Quick Start

### 1. Create namespace and secrets

```bash
# Create the namespace (or let Helm do it)
kubectl create namespace superagente

# Create secrets from your .env file
kubectl create secret generic superagente-secrets \
  --namespace superagente \
  --from-literal=APP_SECRET_KEY='your-fernet-key' \
  --from-literal=DATABASE_URL='postgresql://user:pass@host:5432/superagente' \
  --from-literal=REDIS_URL='redis://redis:6379/0' \
  --from-literal=POSTGRES_PASSWORD='your-db-password' \
  --from-literal=GEMINI_API_KEY='your-key' \
  --from-literal=GROQ_API_KEY='your-key' \
  --from-literal=OPENAI_API_KEY='your-key'
```

### 2. Deploy with Helm

```bash
# Staging
helm upgrade --install superagente ./k8s/helm/superagente \
  -f k8s/environments/staging.yaml \
  -n superagente-staging \
  --create-namespace

# Production
helm upgrade --install superagente ./k8s/helm/superagente \
  -f k8s/environments/production.yaml \
  -n superagente \
  --create-namespace
```

### 3. Verify deployment

```bash
# Check pods
kubectl get pods -n superagente -w

# Check services
kubectl get svc -n superagente

# Check ingress
kubectl get ingress -n superagente

# Check HPA status
kubectl get hpa -n superagente

# Check network policies
kubectl get networkpolicy -n superagente

# View app logs
kubectl logs -n superagente -l app.kubernetes.io/component=app -f
```

## Security Hardening

This chart enforces the **restricted** Pod Security Standard:

| Control | Setting |
|---------|---------|
| Run as non-root | UID 65534 (nobody) |
| Read-only root filesystem | Enabled |
| Privilege escalation | Disabled |
| Capabilities | ALL dropped |
| Seccomp profile | RuntimeDefault |
| Service account token | Not auto-mounted |
| Network policies | Default deny all |

### Network Policy Matrix

| Source | Destination | Ports |
|--------|------------|-------|
| Ingress Controller | App | 8501/TCP |
| App | PostgreSQL | 5432/TCP |
| App | Redis | 6379/TCP |
| App | External HTTPS | 443/TCP |
| App | SMTP | 587/TCP |
| Worker | PostgreSQL | 5432/TCP |
| Worker | Redis | 6379/TCP |
| Worker | External HTTPS | 443/TCP |
| Prometheus | Monitoring | 8080/TCP |
| Monitoring | PostgreSQL | 5432/TCP |
| Monitoring | Redis | 6379/TCP |
| All pods | DNS | 53/UDP+TCP |

## Scaling

### Horizontal Pod Autoscaler

The HPA is configured to scale the app deployment based on:
- **CPU utilization** — target 65-70% (configurable)
- **Memory utilization** — target 75-80% (configurable)

Scale-up stabilization: 30-60s. Scale-down stabilization: 300-600s.

```bash
# View current scaling status
kubectl get hpa -n superagente

# Manual scale override (temporary)
kubectl scale deployment superagente-app --replicas=5 -n superagente
```

### Pod Disruption Budget

- **App**: minAvailable=2 (production), minAvailable=1 (staging)
- **Worker**: minAvailable=1

Ensures high availability during node drains and cluster upgrades.

## Configuration

### Overriding Values

```bash
# Override individual values
helm upgrade superagente ./k8s/helm/superagente \
  -f k8s/environments/production.yaml \
  --set app.replicaCount=5 \
  --set autoscaling.maxReplicas=30

# Dry-run to preview changes
helm upgrade superagente ./k8s/helm/superagente \
  -f k8s/environments/production.yaml \
  --dry-run --debug
```

### Key Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `app.replicaCount` | 2 | App replicas (ignored when HPA is enabled) |
| `worker.replicaCount` | 2 | Worker replicas |
| `autoscaling.enabled` | true | Enable HPA |
| `autoscaling.minReplicas` | 2 | Minimum app replicas |
| `autoscaling.maxReplicas` | 10 | Maximum app replicas |
| `networkPolicy.enabled` | true | Enable network policies |
| `ingress.enabled` | true | Enable ingress |
| `monitoring.enabled` | true | Deploy monitoring sidecar |

## Rollback

```bash
# View release history
helm history superagente -n superagente

# Rollback to previous release
helm rollback superagente -n superagente

# Rollback to specific revision
helm rollback superagente 3 -n superagente
```

## Monitoring

The monitoring deployment exposes:
- `GET /health` — liveness/readiness endpoint
- `GET /metrics` — Prometheus-compatible metrics

Pods are annotated with `prometheus.io/scrape: "true"` for auto-discovery.

```bash
# Port-forward to monitoring service
kubectl port-forward svc/superagente-monitoring 8080:8080 -n superagente

# Check health
curl http://localhost:8080/health

# View metrics
curl http://localhost:8080/metrics
```

## Troubleshooting

```bash
# Describe a failing pod
kubectl describe pod <pod-name> -n superagente

# Check events
kubectl get events -n superagente --sort-by='.lastTimestamp'

# Exec into a pod (requires debug container for read-only FS)
kubectl debug -it <pod-name> -n superagente --image=busybox

# Check resource quotas
kubectl describe resourcequota -n superagente

# Validate templates without deploying
helm template superagente ./k8s/helm/superagente \
  -f k8s/environments/production.yaml | kubectl apply --dry-run=server -f -
```
