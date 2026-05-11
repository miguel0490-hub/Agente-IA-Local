# Auditoría Completa — SuperAgente IA Pro

**Fecha:** 11 de mayo de 2026  
**Versión:** Último commit `69f377b`  
**Autor del análisis:** Auditoría automatizada  

---

## 1. Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Archivos Python | 90 |
| Líneas de código Python | 9.196 |
| Archivos de test | 24 |
| Dependencias de producción | 34 |
| Dependencias de desarrollo | 4 |
| Tablas en base de datos | 4 |
| Proveedores de IA integrados | 6 built-in + ilimitados custom |
| Servicios externos conectados | 14 |

---

## 2. Estructura del Proyecto

```
SuperAgente-IA-Pro/
├── app.py                          # Entrada principal (275 líneas)
├── Dockerfile                      # Imagen Docker para producción
├── docker-compose.yml              # Orquestación con Redis + PostgreSQL
├── requirements.txt                # 34 dependencias de producción
├── requirements-dev.txt            # 4 dependencias de testing
├── pytest.ini                      # Configuración de pytest
├── .env.example                    # Plantilla de variables de entorno
├── .gitignore                      # Exclusiones de Git
├── .dockerignore                   # Exclusiones de Docker
├── .streamlit/
│   └── config.toml                 # Configuración de Streamlit (tema oscuro)
├── scripts/
│   ├── iniciar_agente.bat          # Script de arranque Windows
│   ├── _build_estado_actual.py     # Generador de estado del proyecto
│   ├── manual_full_pipeline.py     # Pipeline manual de testing
│   └── manual_pdfkit_probe.py      # Probe de pdfkit
├── deploy/
│   ├── nginx.conf                  # Config Nginx para reverse proxy
│   └── nginx-ssl.example.conf      # Config Nginx con SSL
├── docs/
│   ├── ARCHITECTURE.md             # Documentación de arquitectura
│   ├── SECURITY_AUDIT.md           # Auditoría de seguridad previa
│   ├── PRODUCTION_DEPLOY.md        # Guía de despliegue
│   ├── DEAD_CODE_SCAN.md           # Análisis de código muerto
│   └── auditoria_post_refactor.md  # Auditoría post-refactorización
├── src/
│   ├── core/                       # Capa núcleo (13 archivos)
│   ├── database/                   # Capa de persistencia (1 archivo)
│   ├── security/                   # Capa de seguridad (3 archivos)
│   ├── services/                   # Capa de servicios (17 archivos)
│   ├── monitoring/                 # API de monitorización (1 archivo)
│   └── ui/                         # Capa de interfaz (29 archivos)
│       ├── admin/                  # Panel de administración
│       ├── auth/                   # Autenticación y registro
│       ├── chat/                   # Runtime de chat y saludos
│       ├── components/             # Componentes reutilizables
│       ├── contact/                # Formulario de contacto
│       ├── multimedia/             # Herramientas multimedia
│       ├── onboarding/             # Configuración inicial de API keys
│       ├── settings/               # Centro de control
│       └── sidebar/                # Sidebar (perfil, chats, roles)
├── tests/                          # Tests unitarios y E2E (24 archivos)
├── generated_images/               # Directorio de imágenes generadas
├── logs/                           # Logs de la aplicación
└── data/                           # Base de datos SQLite (en .gitignore)
```

---

## 3. Arquitectura por Capas

```
┌─────────────────────────────────────────────────────────┐
│                    app.py (Orquestador)                  │
│  Auth → Onboarding → Sidebar → Chat → Multimedia        │
├─────────────────────────────────────────────────────────┤
│                   CAPA UI (src/ui/)                      │
│  auth/ · admin/ · contact/ · chat/ · sidebar/           │
│  settings/ · onboarding/ · multimedia/ · components/     │
├─────────────────────────────────────────────────────────┤
│               CAPA SERVICIOS (src/services/)             │
│  llm_provider · audio · image_gen · converter · email   │
│  web_search · rag · execution_sandbox · upload_security  │
├─────────────────────────────────────────────────────────┤
│                CAPA CORE (src/core/)                     │
│  config · security · auth_cookies · session_state       │
│  intent_parser · logger · observability · sanitizer     │
├─────────────────────────────────────────────────────────┤
│             CAPA SEGURIDAD (src/security/)               │
│  tool_guard · prompt_injection_detector                  │
├─────────────────────────────────────────────────────────┤
│              CAPA DATOS (src/database/)                  │
│  SQLAlchemy (PostgreSQL / SQLite) + Fernet encryption   │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Esquema de Base de Datos

### 4.1 Tabla `users`

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| id | Integer | PK, autoincrement |
| first_name | String(255) | NOT NULL |
| last_name | String(255) | NOT NULL |
| email | String(255) | UNIQUE, NOT NULL |
| username | String(255) | UNIQUE, NOT NULL |
| password_hash | Text | NOT NULL |
| encrypted_api_keys | Text | Cifrado con Fernet AES-128 |
| is_verified | Integer | NOT NULL, default 0 |
| is_admin | Integer | NOT NULL, default 0 |
| is_active | Integer | NOT NULL, default 1 |
| created_at | DateTime | default NOW() |
| verification_token | Text | Token de verificación email |
| verification_token_expires | DateTime | Expiración del token |
| reset_token | Text | Token de reseteo de contraseña |
| reset_token_expires | DateTime | Expiración del token |
| remember_token | Text | Token de "Recuérdame" |
| remember_token_expires | DateTime | Expiración del token |

### 4.2 Tabla `chats`

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| id | Integer | PK, autoincrement |
| user_id | Integer | FK → users.id (CASCADE), NOT NULL |
| title | Text | NOT NULL |
| updated_at | DateTime | default NOW() |

### 4.3 Tabla `messages`

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| id | Integer | PK, autoincrement |
| chat_id | Integer | FK → chats.id (CASCADE), NOT NULL |
| role | String(50) | NOT NULL |
| content | Text | Contenido del mensaje |
| extra_data | Text | JSON blob para metadatos |

### 4.4 Tabla `contact_messages`

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| id | Integer | PK, autoincrement |
| user_id | Integer | FK → users.id (CASCADE), NOT NULL |
| subject | String(255) | NOT NULL |
| message | Text | NOT NULL |
| status | String(50) | NOT NULL, default 'pending' |
| admin_reply | Text | Respuesta del administrador |
| created_at | DateTime | default NOW() |

### 4.5 Tabla RAG (base de datos separada)

| Tabla Virtual | Motor | Columnas |
|---|---|---|
| documents | FTS5 (SQLite) | filename, chunk_text |

---

## 5. Integraciones Externas

### 5.1 Proveedores de IA

| Servicio | SDK/Protocolo | Propósito | Configurable sin código |
|----------|--------------|-----------|------------------------|
| Google Gemini | `google.genai` SDK | Chat multimodal (gemini-2.5-pro) + Imagen (imagen-4.0) | No (built-in) |
| Groq | `groq` SDK | Chat (LLaMA 3.3-70b) + STT (Whisper) | No (built-in) |
| OpenRouter | OpenAI-compatible API | Multi-modelo (gratuitos y de pago) | No (built-in) |
| OpenAI | `openai` SDK | DALL-E 3 (imágenes) + TTS (voz) | No (built-in) |
| Stability AI | REST API | Stable Image Core | No (built-in) |
| Ollama | OpenAI-compatible (localhost) | Modelos locales | No (built-in) |
| Custom OpenAI-compatible | `openai` SDK + base_url custom | Cualquier API compatible OpenAI | **Si** (Centro de Control) |

### 5.2 Otros Servicios

| Servicio | Protocolo | Propósito |
|----------|-----------|-----------|
| Brevo (Sendinblue) | SMTP (TLS 587) | Emails transaccionales (verificación, reset, contacto) |
| Redis | TCP | Rate limiting + cola de tareas (RQ) |
| Sentry | HTTPS | Monitorización de errores y trazas |
| DuckDuckGo | `ddgs` library | Búsqueda web para grounding/RAG |
| Microsoft Edge TTS | `edge_tts` library | Text-to-Speech gratuito |
| ClamAV | CLI (`clamscan`) | Escaneo antivirus de archivos subidos |
| Docker | CLI (`docker run`) | Sandbox de ejecución de código |

---

## 6. Auditoría de Seguridad

### 6.1 Autenticación y Sesiones

| Medida | Implementación | Estado |
|--------|----------------|--------|
| Hash de contraseñas | bcrypt con salt auto-generado | OK |
| Cifrado de API keys en reposo | Fernet (AES-128-CBC) con APP_SECRET_KEY | OK |
| Cookies de sesión | `Secure`, `SameSite=Strict`, `HttpOnly` | OK |
| Rotación de tokens | Token de "remember me" se rota en cada restauración de sesión | OK |
| Expiración de sesión por inactividad | Configurable (default 120 min) | OK |
| Limpieza de tokens expirados | `cleanup_expired_tokens()` en cada arranque | OK |
| Verificación de email obligatoria | No se permite login sin email verificado | OK |
| Suspensión de cuentas | Flag `is_active`, verificado en cada login | OK |

### 6.2 Rate Limiting

| Ámbito | Límite Default | Ventana | Backend |
|--------|---------------|---------|---------|
| Chat | 10 req | 60s | Redis / In-memory |
| Uploads | 20 req | 300s | Redis / In-memory |
| Tools | 30 req | 300s | Redis / In-memory |
| Login (global) | 8 req | 300s | Redis / In-memory |
| Login (por IP) | 8 req | 300s | Redis / In-memory |
| Login (por usuario) | 8 req | 300s | Redis / In-memory |

Protecciones adicionales:
- Backoff exponencial en login fallido (base 2s, max 60s, trigger tras 3 fallos)
- `LOGIN_REQUIRE_REDIS=1` impide fallback a in-memory en producción

### 6.3 Seguridad de Uploads

| Capa | Protección |
|------|-----------|
| 1 | Blocklist de extensiones peligrosas (.exe, .dll, .bat, .cmd, .ps1, .js, .jar, .msi) |
| 2 | Allowlist de extensiones permitidas (modo strict) |
| 3 | Límites de tamaño por categoría (imagen 15MB, video 100MB, audio 100MB, docs 25MB) |
| 4 | Verificación de magic bytes (firma binaria vs extensión declarada) |
| 5 | Detección de ZIP bombs (>250MB descomprimido o ratio >100:1) |
| 6 | Escaneo antivirus con ClamAV (opcional, cuarentena automática) |
| 7 | Política configurable: `strict` (producción) vs `permissive` (desarrollo) |

### 6.4 Sandbox de Ejecución de Código

| Restricción | Valor |
|-------------|-------|
| Red | `--network none` (sin internet) |
| Filesystem | `--read-only` |
| Procesos | `--pids-limit 64` |
| CPU | `--cpus 0.50` |
| Memoria | `--memory 256m` |
| Privilegios | `--cap-drop ALL`, `--security-opt no-new-privileges` |
| Usuario | Unprivileged (65534:65534) |
| Timeout | 8 segundos |
| Pre-validación | AST-level: bloquea imports peligrosos (`os`, `sys`, `subprocess`, `eval`, `exec`, `open`) |

### 6.5 Protección contra Inyección de Prompts

- Detector regex de patrones comunes de jailbreak
- Patrones detectados: "ignore all previous instructions", "system instruction override", "reveal the system prompt", "dump/exfiltrate/steal secrets", "disable safety"
- Protocolo anti-jailbreak embebido en los system prompts de cada rol

### 6.6 Tool Guard (Control de Herramientas)

| Categoría | Acciones | Comportamiento |
|-----------|----------|----------------|
| HARD_BLOCKED | `shell`, `filesystem`, `delete_file`, `run_system_command` | Siempre denegado |
| SENSITIVE | `execute_code`, `open_converter` | Requiere confirmación explícita del usuario |

### 6.7 Otras Medidas

| Medida | Ubicación |
|--------|-----------|
| Sanitización HTML/XSS via bleach | `src/core/sanitizer.py` |
| Redacción de secretos en Sentry | `src/core/observability.py` |
| `send_default_pii=False` en Sentry | `src/core/observability.py` |
| Extracción segura de IP (X-Forwarded-For, X-Real-IP) | `src/core/request_context.py` |

---

## 7. Proveedores de IA — Arquitectura

### 7.1 Patrón Factory

```
LLMProvider (clase base abstracta)
├── GeminiProvider        → google.genai SDK (propietario)
├── GroqProvider          → groq SDK (compatible OpenAI)
├── OpenRouterProvider    → openai SDK (base_url custom)
├── OllamaProvider        → openai SDK (localhost)
└── CustomOpenAIProvider  → openai SDK (base_url del usuario)
```

### 7.2 Escalabilidad

- **Sin código:** Cualquier API compatible con OpenAI (DeepSeek, Mistral, Together AI, Fireworks, Perplexity, xAI, LM Studio, vLLM, Anthropic Claude, Cohere) se registra desde el Centro de Control.
- **Con código (3-4 archivos):** Solo para SDKs propietarios no compatibles con OpenAI (Amazon Bedrock, Google Vertex AI).
- **Cobertura estimada:** ~95% de los proveedores de IA del mercado sin tocar código.

### 7.3 Capacidades Multimedia

| Capacidad | Proveedor | Entrada | Salida |
|-----------|-----------|---------|--------|
| Chat de texto | Gemini, Groq, OpenRouter, Ollama, Custom | Texto | Texto (streaming) |
| Chat multimodal | Gemini | Texto + Imágenes + Video | Texto (streaming) |
| Generación de imágenes | Gemini (Imagen 4.0), OpenAI (DALL-E 3), Stability AI | Prompt de texto | Imagen PNG/JPEG |
| Transcripción STT | Groq (Whisper) | Audio (mp3, wav, etc.) | Texto |
| Text-to-Speech | OpenAI TTS, Microsoft Edge TTS | Texto | Audio MP3 |
| Búsqueda web | DuckDuckGo | Query | Resultados contextuales |
| RAG (indexación) | FTS5 SQLite | Documentos PDF/TXT | Chunks indexados |
| Conversión de archivos | converter_service | Múltiples formatos | PDF, DOCX, etc. |

---

## 8. Variables de Entorno

### 8.1 Core

| Variable | Propósito | Default |
|----------|-----------|---------|
| `APP_SECRET_KEY` | Clave Fernet para cifrar API keys | Requerido |
| `DATABASE_URL` | Conexión SQLAlchemy | `sqlite:///data/superagente.db` |
| `REDIS_URL` | Conexión Redis | `redis://redis:6379/0` |
| `ENVIRONMENT` | Modo de ejecución | `production` |

### 8.2 Seguridad

| Variable | Propósito | Default |
|----------|-----------|---------|
| `UPLOAD_POLICY` | Política de uploads | `strict` |
| `MAX_IMAGE_MB` / `MAX_VIDEO_MB` / `MAX_AUDIO_MB` / `MAX_DOC_MB` | Límites de tamaño | 15 / 100 / 100 / 25 |
| `RATE_LIMIT_CHAT_LIMIT` / `_WINDOW` | Rate limit chat | 10 / 60s |
| `RATE_LIMIT_UPLOADS_LIMIT` / `_WINDOW` | Rate limit uploads | 20 / 300s |
| `RATE_LIMIT_TOOLS_LIMIT` / `_WINDOW` | Rate limit tools | 30 / 300s |
| `RATE_LIMIT_LOGIN_LIMIT` / `_WINDOW` | Rate limit login global | 8 / 300s |
| `LOGIN_BACKOFF_*` | Config de backoff exponencial | Base 2s, Max 60s, Trigger 3 |
| `LOGIN_REQUIRE_REDIS` | Exigir Redis para login | `1` |
| `REMEMBER_ME_DAYS` | Duración cookie remember me | 7 |
| `SESSION_IDLE_TIMEOUT_MINUTES` | Timeout inactividad | 120 |

### 8.3 Proveedores de IA

| Variable | Propósito |
|----------|-----------|
| `GEMINI_API_KEY` / `_MAX_TOKENS` / `_TEMPERATURE` | Google Gemini |
| `GROQ_API_KEY` / `_MODEL` / `_FALLBACK_MODEL` / `_MAX_TOKENS` / `_TEMPERATURE` / `_CONTINUATION_ROUNDS` | Groq |
| `OPENROUTER_API_KEY` / `_MAX_TOKENS` / `_TEMPERATURE` / `_CONTINUATION_ROUNDS` | OpenRouter |
| `CUSTOM_OPENAI_MAX_TOKENS` / `_TEMPERATURE` | Custom OpenAI-compatible |
| `OLLAMA_MAX_TOKENS` / `_TEMPERATURE` | Ollama local |
| `OPENAI_API_KEY` | OpenAI (DALL-E 3 + TTS) |
| `STABILITY_API_KEY` | Stability AI |

### 8.4 Servicios

| Variable | Propósito |
|----------|-----------|
| `SMTP_SERVER` / `_PORT` / `_USER` / `_PASSWORD` / `_FROM` | Email via Brevo |
| `CLAMSCAN_BIN` | Ruta al binario ClamAV |
| `SENTRY_DSN` / `_TRACES_SAMPLE_RATE` | Monitorización Sentry |
| `ENABLE_ASYNC_TASKS` / `RQ_QUEUE_NAME` | Cola de tareas Redis |

---

## 9. Testing

### 9.1 Cobertura de Tests

| Archivo de Test | Módulo Cubierto |
|-----------------|-----------------|
| `test_core_security.py` | Rate limiting, backoff, login security |
| `test_upload_security.py` + `_coverage.py` | Validación de uploads, magic bytes, ZIP bombs |
| `test_file_validator.py` + `_coverage.py` | Validación de archivos |
| `test_file_factory_*.py` (2 archivos) | Generación de PDFs y layouts |
| `test_execution_sandbox.py` + `_coverage.py` | Sandbox Docker |
| `test_tool_guard.py` + `_coverage.py` | Tool guard policies |
| `test_sanitizer.py` | Sanitización HTML/XSS |
| `test_observability.py` | Sentry integration |
| `test_llm_pipeline.py` | Pipeline de LLM providers |
| `test_provider_greetings.py` | Saludos de proveedores |
| `test_runtime_tool_intent.py` | Parsing de intenciones |
| `test_parser_fix.py` | Intent parser |
| `test_agent_tools_coverage.py` | Agent tools |
| `test_document_parser_async.py` | Parser de documentos |
| `test_request_context.py` | Extracción de IP |
| `test_task_queue.py` | Cola de tareas |
| `test_remote_apis.py` | APIs remotas |
| `tests/e2e/test_agent_flows.py` | Flujos E2E con Playwright |

### 9.2 CI/CD

- **GitHub Actions**: Pipeline automatizado en `.github/workflows/ci.yml`
- Instala dependencias de producción y desarrollo
- Instala Playwright browsers (Chromium)
- Ejecuta pytest con cobertura
- Variable `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` para compatibilidad

---

## 10. Despliegue

### 10.1 Docker

- `Dockerfile`: Imagen basada en Python con todas las dependencias
- `docker-compose.yml`: Orquestación con Redis + PostgreSQL
- `deploy/nginx.conf`: Reverse proxy con Nginx
- `deploy/nginx-ssl.example.conf`: Configuración SSL

### 10.2 Local (Windows)

- `scripts/iniciar_agente.bat`: Script de arranque que activa venv y lanza Streamlit

---

## 11. Historial de Cambios Recientes

| Commit | Descripción |
|--------|-------------|
| `69f377b` | Menú hamburguesa en tarjeta de perfil (sidebar limpia) |
| `0117109` | Fix estilos de botones en dialogs |
| `950273d` | Notificaciones de contacto a SMTP_FROM |
| `c90a906` | Migración automática de tabla contact_messages |
| `2a0af1a` | Sistema de contacto usuario-admin completo |
| `9c85c1c` | Fix CSS de visibilidad en admin panel |
| `00d0f43` | Panel de administración con dashboard y gestión de usuarios |
| `a9ad7ea` | Migración SMTP a Brevo con SMTP_FROM configurable |
| `eaae43f` | Fix CI/CD: dependencias de desarrollo + Playwright |

---

## 12. Conclusiones

### Fortalezas
- Arquitectura modular bien separada por capas
- Seguridad multi-capa robusta (bcrypt, Fernet, rate limiting, sandbox Docker, ClamAV)
- Escalabilidad de proveedores de IA (~95% sin tocar código)
- Sistema de administración completo con dashboard y gestión de usuarios
- CI/CD automatizado con GitHub Actions
- Soporte dual de base de datos (PostgreSQL producción / SQLite desarrollo)
- 24 archivos de tests cubriendo módulos críticos

### Puntos de Mejora Potenciales
- Factory de proveedores usa string matching en lugar de registry pattern
- Nombres de motores hardcodeados como "magic strings" en varios archivos
- No hay sistema de notificaciones en tiempo real (push/websocket)
- No hay paginación en la gestión de usuarios del admin panel
- No hay backup automatizado de base de datos
- No hay logs de auditoría de acciones administrativas
