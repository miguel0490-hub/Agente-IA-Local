# Despliegue local (Docker Compose)

## Requisitos previos

- Docker Desktop (o Docker Engine + Compose v2)
- Archivo `.env` en la raíz del repo (copia desde `.env.example`)

## Variables obligatorias para `docker compose`

Compose falla al interpolar si faltan estas claves (sintaxis `:?` en `docker-compose.yml`):

| Variable | Uso |
|----------|-----|
| `POSTGRES_PASSWORD` | Postgres y `DATABASE_URL` de app/worker/gateway |
| `REDIS_PASSWORD` | Redis con `--requirepass` y `REDIS_URL` con credencial |
| `GRAFANA_ADMIN_PASSWORD` | Usuario admin de Grafana |
| `APP_SECRET_KEY` | Clave Fernet (app Streamlit y cifrado) |
| `SERVICE_JWT_SECRET` | JWT entre servicios (según uso en gateway/monitoring) |

Copia `.env.example` a `.env` y sustituye los placeholders `replace_with_*`.

## Arranque

```bash
docker compose down
docker compose up -d --build
```

Streamlit queda en **http://127.0.0.1:8501** (mapeo directo del servicio `app`).  
La entrada unificada por **Nginx** es **http://127.0.0.1/** (puerto 80).

Otros puertos publicados en localhost:

| Puerto | Servicio |
|--------|----------|
| 80 | Nginx (reverse proxy) |
| 8501 | App Streamlit |
| 3000 | Grafana |
| 9090 | Prometheus |

API gateway (interno al compose): puerto 8000; health interno `http://127.0.0.1:8000/api/v1/health`. Monitoring (uvicorn): `http://127.0.0.1:8080/health` detrás de la red Docker; Nginx enruta según `deploy/nginx.conf`.

## Healthchecks

- **postgres**: `pg_isready`
- **redis**: `redis-cli -a … ping` debe devolver `PONG`
- **app / gateway / monitoring**: `curl` a rutas de health
- **worker**: `python -c` con `redis.from_url(...).ping()`
- **prometheus**: `wget` a `/-/healthy`
- **grafana**: `wget` + `grep` sobre JSON de `/api/health` (campo `database`)

Comprobar estado: `docker compose ps` (todos `healthy` cuando el arranque ha terminado).

## Desarrollo sin Docker

```bash
pip install -r requirements.txt
streamlit run app.py
```

Sin `DATABASE_URL` de Postgres, la app puede usar SQLite en `data/superagente.db` (ver comentarios en `.env.example`). Ajusta `LOGIN_REQUIRE_REDIS` si no tienes Redis local.

## Tests (pytest)

`tests/conftest.py` fuerza `DATABASE_URL` a `sqlite:///data/pytest_automation.db` y ejecuta `init_db()` al inicio de sesión, salvo `PYTEST_USE_PG_DATABASE=1` (Postgres real para integración profunda).

Misma política de cobertura que CI: `python -m pytest --ignore=tests/e2e --ignore=tests/load --cov-fail-under=100`. Para un subconjunto sin umbral: `pytest ruta/al/test.py --no-cov`.

## Logs y avisos aceptables

Tras `docker compose up -d`, revisa `docker compose logs --tail=50 grafana` (y `worker`, `app`). Grafana puede registrar avisos de plugins o analytics si algún panel legacy referencia plugins deshabilitados; lo importante es que el contenedor pase a `healthy` y la UI responda en el puerto 3000.
