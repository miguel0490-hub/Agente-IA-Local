# Despliegue en producción — checklist

## Antes de exponer a Internet

1. **Variables de entorno** según `.env.example`: `APP_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `ENVIRONMENT=production`, `UPLOAD_POLICY=strict`.
2. **Redis** para límites de login y tareas en segundo plano: usar **`LOGIN_REQUIRE_REDIS=1`** en producción (fail-closed si Redis cae). En desarrollo local puedes poner `0`.
3. **TLS y HSTS:** terminar HTTPS en Nginx, CDN o balanceador; no servir solo HTTP público. Plantilla de referencia: `deploy/nginx-ssl.example.conf` (certificados PEM + `Strict-Transport-Security`).
4. **Puertos:** en Compose, exponer al host solo lo necesario: **Nginx (80/443)**; Streamlit queda en **`127.0.0.1:8501`** solo para depuración local; monitoring sin puerto publicado (solo red interna).
5. **Cookies:** en HTTPS, las cookies seguras (`Secure`) funcionan correctamente vía `auth_cookies.set_auth_cookie`.
6. **Backups:** `data/` (SQLite) y política de retención de `generated_images/` y `logs/`.

## Paquetes del sistema (opcional)

Para conversiones/PDF en una imagen Docker derivada o en el host (no están en `requirements.txt`): `ffmpeg`, `libmagic1`, `pandoc`, `wkhtmltopdf`. Instálalos según tu distro.

## CI

GitHub Actions (`.github/workflows/ci.yml`): tests con cobertura y **`pip-audit`** sobre `requirements.txt`.

## Verificación rápida post-deploy

- Cabeceras de seguridad en respuestas HTML (vía Nginx).
- `GET /health` vía origen público devuelve `{"status":"ok"}`.
- `GET /metrics` desde fuera → **403** (configuración actual de Nginx).
- Login: tras varios fallos, backoff y mensajes de rate limit coherentes.
