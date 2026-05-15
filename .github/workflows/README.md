# GitHub Actions — SuperAgente IA Pro

## Workflow principal

**[pipeline.yml](./pipeline.yml)** — `SuperAgente Pipeline`

| Fase | Jobs |
|------|------|
| Calidad | CSS vs theme, preflight, deps mínimas |
| Tests | unit (cobertura 100%), integration, chaos, performance |
| Seguridad | pip-audit, Bandit, Gitleaks, Dependency Review (PR) |
| Docker | build + Trivy HIGH/CRITICAL |
| Supply chain | SBOM CycloneDX, push GHCR, Cosign, provenance |
| Deploy | staging → production (environments con aprobación) |

### Disparadores

- **Push / PR** a `master` o `main`
- **Manual** (`workflow_dispatch`): opción `run_e2e` para Playwright, `skip_deploy` para no desplegar

### Secrets recomendados

| Secret | Uso |
|--------|-----|
| `GITLEAKS_LICENSE` | Gitleaks (opcional) |
| `GEMINI_API_KEY` | Tests E2E manuales |
| `STAGING_HOST`, `STAGING_SSH_KEY` | Environment **staging** |
| `PRODUCTION_HOST`, `PRODUCTION_SSH_KEY` | Environment **production** |

Crea los environments en **Settings → Environments** y activa **Required reviewers** en `production`.

### Dependency Review en PRs

Activa **Settings → Code security → Dependency graph** en el repositorio. Si está desactivado, el job `Dependency Review` muestra aviso pero no bloquea el pipeline.

## Workflows legacy

`ci.yml`, `deploy.yml` y `supply-chain.yml` quedan solo con disparo manual para no duplicar ejecuciones. Usa siempre **SuperAgente Pipeline**.
