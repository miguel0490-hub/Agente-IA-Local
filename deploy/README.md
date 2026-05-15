# Despliegue SuperAgente IA Pro

## Arranque estándar (HTTP, desarrollo/staging)

```bash
cp .env.example .env   # editar secretos
docker compose up -d --build
```

## TLS en producción

1. Copia `nginx.ssl.conf.example` → `nginx.ssl.conf` y cambia `tu-dominio.com`.
2. Crea carpetas: `mkdir -p deploy/certbot/www deploy/certbot/conf`
3. Levanta nginx en HTTP para el reto ACME:
   ```bash
   docker compose up -d nginx
   ```
4. Emite certificado (sustituye dominio y email en `.env`):
   ```bash
   export NGINX_SSL_DOMAIN=tu-dominio.com
   export LETSENCRYPT_EMAIL=admin@tu-dominio.com
   docker compose -f docker-compose.yml -f docker-compose.ssl.yml --profile ssl-init run --rm certbot
   ```
5. Producción con HTTPS:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d
   ```

## Backups PostgreSQL

```bash
export DATABASE_URL=postgresql://superagente:PASSWORD@localhost:5432/superagente
./scripts/backup_postgres.sh
```

Programar con cron (diario, 03:00):

```cron
0 3 * * * cd /ruta/al/proyecto && DATABASE_URL=... ./scripts/backup_postgres.sh
```

## Preflight

```bash
./scripts/preflight_deploy.sh
```
