# Auditoría de seguridad — SuperAgente IA Pro

**Ámbito:** revisión estática del código y configuración de despliegue en el repositorio (sin pentest externo ni revisión de infraestructura física).

**Fecha de referencia:** 2026-05-10.

---

## Resumen ejecutivo

La aplicación incorpora controles relevantes (subidas con política `UPLOAD_POLICY`, rate limiting por ámbito, límites de login con backoff, opción `LOGIN_REQUIRE_REDIS`, cookies endurecidas, sandbox de ejecución, detección de inyección en prompts, métricas bloqueadas en Nginx público). Siguen existiendo riesgos típicos de apps Streamlit autoalojadas: superficie amplia en el mismo proceso, CSP relajada por necesidades de JS inline del framework, y dependencia de configuración correcta (`APP_SECRET_KEY`, TLS, Redis en producción).

---

## Hallazgos por severidad

### Alto

| ID | Hallazgo | Estado / mitigación |
|----|-----------|---------------------|
| H1 | **Streamlit expone una superficie grande** (WS, uploads, estado en servidor). Un bug en la app puede impactar toda la sesión. | Mitigar con actualizaciones de Streamlit, límites de upload, sandbox para código, y despliegue detrás de Nginx + TLS. |
| H2 | **Secretos y claves API** dependen de variables de entorno; si `.env` filtra o imagen Docker incluye secretos, hay compromiso total. | `.gitignore` incluye `.env`; validar CI/CD y no copiar `.env` en capas Docker innecesarias. |
| H3 | **`monitoring` (FastAPI)** escuchaba en `0.0.0.0`** con puerto publicado en el host en `docker-compose`**, ampliando superficie (métricas/salud). | Corregido: el servicio ya no publica `8080` al host; solo la red interna de Compose y Nginx. |

### Medio

| ID | Hallazgo | Recomendación |
|----|-----------|----------------|
| M1 | CSP en Nginx permite `'unsafe-inline'` y `'unsafe-eval'` (típico con Streamlit). | Aceptado como trade-off; endurecer solo si se prueba sin romper UI. |
| M2 | **Ejecución de código** en sandbox (`exec` controlado) sigue siendo riesgo si las reglas se relajan. | Mantener tests de `execution_sandbox` y revisiones en cambios de política. |
| M3 | **Subprocess** (conversión, antivirus opcional) debe mantener rutas y timeouts acotados. | Ya hay validadores; revisar cada nuevo comando. |

### Bajo / operativa

| ID | Hallazgo | Recomendación |
|----|-----------|----------------|
| L1 | `except: pass` en limpieza de temporales ocultaba errores de I/O. | Corregido en `app.py` (log explícito de fallos). |
| L2 | Archivos de cuarentena / DB locales no deben versionarse. | Reforzado `.gitignore` (cobertura, cachés, cuarentena). |

---

## Controles ya implementados (referencia)

- Rate limiting por ámbito (`src/core/security.py`) con Redis opcional y memoria como respaldo (login puede exigir Redis).
- Login: límite por IP y usuario, backoff exponencial, mensaje claro si Redis obligatorio y no disponible.
- Cookies de sesión / remember-me endurecidas (`auth_cookies`, rotación en auto-login).
- Uploads: política estricta/permissiva y límites por tipo (`file_validator`).
- Nginx: cabeceras de seguridad, `/metrics` → 403 en borde.

---

## Roadmap recomendado (post-auditoría)

1. Terminar **HTTPS** en el proxy y habilitar **HSTS** cuando el certificado sea estable.
2. **`LOGIN_REQUIRE_REDIS=1`** en producción con Redis gestionado y alertas si cae.
3. Revisión periódica de **dependencias** (`pip audit` / Dependabot).
4. Opcional: **WAF** o reglas Cloudflare delante del origen.

---

## Limpieza de artefactos locales (mantenimiento)

En el repositorio no deben versionarse: `__pycache__/`, `.pytest_cache/`, `.coverage`, logs locales, ni muestras en `data/quarantine/` (solo la carpeta vacía + `.gitkeep`). Documentación obsoleta duplicada del código de aplicación debe eliminarse para evitar confusiones en auditorías futuras.

## Limitaciones de esta auditoría

No se ejecutó análisis dinámico contra un entorno real, ni revisión de proveedor cloud, ni cumplimiento legal (RGPD, etc.). Los hallazgos deben complementarse con pruebas en el entorno objetivo.
