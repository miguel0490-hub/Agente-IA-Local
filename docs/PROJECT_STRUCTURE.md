# SuperAgente IA Pro — Documentación Técnica Completa

> **Versión:** Mayo 2026  
> **Stack principal:** Python 3.11 · Streamlit · Google Gemini · Groq · OpenRouter · PostgreSQL · Redis · Docker · Kubernetes  
> **Líneas de código fuente:** ~9,200+ (sin tests ni config)

---

## 1. Visión General

**SuperAgente IA Pro** es una plataforma de inteligencia artificial multimodal construida sobre Streamlit que integra múltiples proveedores LLM (Gemini, Groq, OpenRouter, Ollama y cualquier endpoint compatible con OpenAI). Ofrece generación de texto, imágenes, documentos PDF/Excel/HTML, transcripción de audio, síntesis de voz, búsqueda web, ejecución de código en sandbox, análisis RAG de documentos, y un sistema completo de seguridad Zero-Trust.

---

## 2. Árbol de Directorios

```
SuperAgente IA Pro/
│
├── app.py                          # Punto de entrada principal (180 líneas)
├── requirements.txt                # Dependencias de producción (44 paquetes)
├── requirements-dev.txt            # Dependencias de desarrollo/testing
├── Dockerfile                      # Multi-stage build (builder + runtime slim)
├── docker-compose.yml              # Stack completo: app + postgres + redis + worker + gateway + nginx + prometheus + grafana
├── alembic.ini                     # Configuración de migraciones de BD
├── pytest.ini                      # Configuración de pytest
│
├── .github/workflows/
│   ├── ci.yml                      # CI: tests, pip-audit, Vulture, Bandit SAST, Gitleaks, Trivy
│   ├── dependency-review.yml       # Revisión de dependencias en PRs
│   ├── deploy.yml                  # Pipeline de despliegue
│   └── supply-chain.yml           # Seguridad de cadena de suministro (SBOM, Cosign)
│
├── .streamlit/
│   └── config.toml                 # Tema visual + configuración del servidor Streamlit
│
├── src/                            # ===== CÓDIGO FUENTE PRINCIPAL =====
│   ├── __init__.py
│   │
│   ├── core/                       # --- Núcleo de la aplicación ---
│   │   ├── agent_tools.py          # Parser de tool calls JSON del LLM (189 líneas)
│   │   ├── auth_cookies.py         # Gestión de cookies de autenticación (29 líneas)
│   │   ├── bootstrap.py            # Inicialización de app: BD, directorios, GC (37 líneas)
│   │   ├── cache.py                # TTL cache en memoria (61 líneas)
│   │   ├── config.py               # CSS global, prompts del sistema, constantes (830 líneas)
│   │   ├── http_resilience.py      # Reintentos HTTP con backoff exponencial (120 líneas)
│   │   ├── i18n.py                 # Framework de internacionalización con t() (59 líneas)
│   │   ├── intent_parser.py        # Clasificador de intenciones del usuario (17 líneas)
│   │   ├── logger.py               # Logger estructurado con rotación de ficheros (60 líneas)
│   │   ├── observability.py        # Init de Sentry + OpenTelemetry (43 líneas)
│   │   ├── request_context.py      # Context vars para trazabilidad de requests (40 líneas)
│   │   ├── sanitizer.py            # Sanitización de Markdown contra XSS (40 líneas)
│   │   ├── schemas.py              # Modelos Pydantic para validación de datos (65 líneas)
│   │   ├── security.py             # Hashing bcrypt, tokens JWT, cifrado Fernet (184 líneas)
│   │   ├── session_manager.py      # Cookie manager, idle timeout, auto-login (53 líneas)
│   │   ├── session_state.py        # Inicialización de st.session_state (27 líneas)
│   │   ├── settings.py             # Pydantic Settings centralizado (67 líneas)
│   │   └── ui_helpers.py           # Helper para botón de descarga de archivos (28 líneas)
│   │
│   ├── database/                   # --- Capa de persistencia ---
│   │   └── database.py             # SQLAlchemy: usuarios, chats, mensajes, API keys, usage_log (751 líneas)
│   │
│   ├── services/                   # --- Servicios de negocio ---
│   │   ├── audio_service.py        # Transcripción Whisper + síntesis TTS (146 líneas)
│   │   ├── background_tasks.py     # Tareas asíncronas con RQ/Redis (17 líneas)
│   │   ├── context_manager.py      # Gestión de contexto conversacional (68 líneas)
│   │   ├── converter_service.py    # Conversión entre formatos de archivo (66 líneas)
│   │   ├── cost_tracker.py         # Tracking de coste/uso de tokens por proveedor (93 líneas)
│   │   ├── document_parser.py      # Parser de PDF, DOCX, XLSX, PPTX, ODS, CSV (247 líneas)
│   │   ├── email_service.py        # Envío de emails SMTP (recuperación de contraseña) (126 líneas)
│   │   ├── execution_sandbox.py    # Sandbox seguro para ejecución de código Python (146 líneas)
│   │   ├── execution_service.py    # Orquestador de ejecución de código (19 líneas)
│   │   ├── file_factory.py         # Generador de PDF, HTML, Excel, Markdown (529 líneas)
│   │   ├── file_validator.py       # Validación de archivos subidos (tipo, tamaño, magic bytes) (180 líneas)
│   │   ├── image_gen_service.py    # Generación de imágenes con Gemini Imagen + Stability AI (132 líneas)
│   │   ├── llm_provider.py         # Abstracción de proveedores LLM: Gemini, Groq, OpenRouter, Ollama, Custom (503 líneas)
│   │   ├── memory_service.py       # Persistencia de historial de chat en BD (123 líneas)
│   │   ├── model_router.py         # Router inteligente de modelos según carga/costo (183 líneas)
│   │   ├── provider_factory.py     # Factory para instanciar proveedores multimedia (29 líneas)
│   │   ├── rag_service.py          # Servicio RAG: indexación y consulta sobre documentos (65 líneas)
│   │   ├── sandbox_config.py       # Configuración del sandbox (permisos, límites) (130 líneas)
│   │   ├── sandbox_runtime.py      # Runtime del sandbox con Docker/proceso aislado (209 líneas)
│   │   ├── semantic_cache.py       # Caché semántica de respuestas LLM (135 líneas)
│   │   ├── task_queue.py           # Cola de tareas Redis/RQ (70 líneas)
│   │   ├── tenant.py               # Multi-tenancy: aislamiento de datos por organización (212 líneas)
│   │   ├── tool_sandbox.py         # Sandboxing de herramientas del agente (126 líneas)
│   │   ├── upload_security.py      # Validación de seguridad de archivos subidos (44 líneas)
│   │   └── web_search.py           # Búsqueda web vía DuckDuckGo (36 líneas)
│   │
│   ├── security/                   # --- Capa de seguridad ---
│   │   ├── ai_firewall.py          # Firewall de IA: detección de ataques adversariales (294 líneas)
│   │   ├── llm_firewall.py         # Filtrado de salidas LLM peligrosas (54 líneas)
│   │   ├── path_guard.py           # Protección contra path traversal (67 líneas)
│   │   ├── policy_engine.py        # Motor de políticas de seguridad configurables (200 líneas)
│   │   ├── prompt_injection_detector.py  # Detector de inyección de prompts (104 líneas)
│   │   ├── secrets_manager.py      # Gestión segura de secretos con cifrado (168 líneas)
│   │   ├── tool_guard.py           # Control de acceso a herramientas del agente (75 líneas)
│   │   ├── url_validator.py        # Validación de URLs contra SSRF (123 líneas)
│   │   └── zero_trust.py           # Middleware Zero-Trust: autenticación + rate limiting (172 líneas)
│   │
│   ├── compliance/                 # --- Cumplimiento normativo ---
│   │   ├── audit_log.py            # Log de auditoría inmutable (195 líneas)
│   │   ├── data_classification.py  # Clasificación de datos sensibles (106 líneas)
│   │   └── gdpr.py                 # Cumplimiento GDPR: exportación/eliminación de datos (327 líneas)
│   │
│   ├── observability/              # --- Monitorización y alertas ---
│   │   ├── ai_metrics.py           # Métricas Prometheus para LLM (latencia, tokens, costes) (150 líneas)
│   │   ├── alerting.py             # Sistema de alertas configurable (173 líneas)
│   │   ├── tracing.py              # OpenTelemetry distributed tracing (113 líneas)
│   │   └── dashboards/
│   │       ├── grafana_cost.json   # Dashboard Grafana: costes por proveedor
│   │       ├── grafana_llm.json    # Dashboard Grafana: rendimiento LLM
│   │       └── grafana_security.json # Dashboard Grafana: eventos de seguridad
│   │
│   ├── gateway/                    # --- API Gateway ---
│   │   └── app.py                  # FastAPI gateway con rate limiting + Zero-Trust (190 líneas)
│   │
│   ├── monitoring/                 # --- Endpoint de métricas ---
│   │   └── api.py                  # API de métricas Prometheus (48 líneas)
│   │
│   └── ui/                         # --- Interfaz de usuario ---
│       ├── dialogs.py              # Factory de diálogos Streamlit (55 líneas)
│       ├── pwa.py                  # Inyección de meta tags PWA (15 líneas)
│       │
│       ├── admin/
│       │   └── admin_panel.py      # Panel de administración: dashboard, gestión de usuarios, mensajes (247 líneas)
│       │
│       ├── auth/
│       │   ├── auth_gate.py        # Login/registro con remember-me y recuperación de contraseña (129 líneas)
│       │   └── query_params_gate.py # Manejo de tokens en URL (reset password) (32 líneas)
│       │
│       ├── chat/
│       │   ├── runtime.py          # Orquestador del chat: streaming, tools, fallback, caché (355 líneas)
│       │   └── provider_greetings.py # Mensajes de bienvenida por proveedor (128 líneas)
│       │
│       ├── components/
│       │   ├── chat_messages.py    # Renderizado de mensajes con filtrado de JSON interno (58 líneas)
│       │   ├── header.py           # Header principal de la aplicación (14 líneas)
│       │   └── notifications.py    # Centro de notificaciones in-app (59 líneas)
│       │
│       ├── contact/
│       │   └── contact_form.py     # Formulario de contacto con envío de email (84 líneas)
│       │
│       ├── multimedia/
│       │   ├── converter_dialog.py # Diálogo de conversión universal de formatos (84 líneas)
│       │   └── sidebar_tools.py    # Herramientas multimedia: Whisper STT, TTS, generación de imágenes (204 líneas)
│       │
│       ├── onboarding/
│       │   └── onboarding_gate.py  # Wizard de configuración inicial de API keys (162 líneas)
│       │
│       ├── settings/
│       │   └── control_center.py   # Centro de control: IAs externas, claves, cuenta, idioma (177 líneas)
│       │
│       └── sidebar/
│           ├── chat_management.py  # Gestión de chats: crear, buscar, renombrar, exportar (119 líneas)
│           ├── main_panel.py       # Panel principal del sidebar: rol, motor, archivos, herramientas (111 líneas)
│           ├── mobile_behavior.py  # Auto-colapso del sidebar en móvil (36 líneas)
│           ├── profile.py          # Tarjeta de perfil + menú hamburguesa (75 líneas)
│           └── roles.py            # Definición de roles del agente (33 líneas)
│
├── tests/                          # ===== SUITE DE TESTS =====
│   ├── conftest.py                 # Fixtures compartidos
│   ├── e2e/
│   │   └── test_agent_flows.py     # Tests end-to-end con Playwright
│   ├── load/
│   │   └── locustfile.py           # Tests de carga con Locust
│   ├── test_agent_tools_coverage.py
│   ├── test_ai_functional_audit.py
│   ├── test_ai_security.py
│   ├── test_chaos.py               # Tests de caos/resiliencia
│   ├── test_compliance.py
│   ├── test_core_security.py
│   ├── test_cost_optimization.py
│   ├── test_document_parser_async.py
│   ├── test_execution_sandbox.py
│   ├── test_execution_sandbox_coverage.py
│   ├── test_file_factory_layout_guardrails.py
│   ├── test_file_factory_pdf_fallback.py
│   ├── test_file_validator.py
│   ├── test_file_validator_coverage.py
│   ├── test_gateway.py
│   ├── test_http_resilience.py
│   ├── test_llm_pipeline.py
│   ├── test_multitenancy.py
│   ├── test_observability.py
│   ├── test_parser_fix.py
│   ├── test_path_traversal.py
│   ├── test_prompt_injection_v2.py
│   ├── test_provider_greetings.py
│   ├── test_remote_apis.py
│   ├── test_request_context.py
│   ├── test_runtime_tool_intent.py
│   ├── test_sandbox_hardening.py
│   ├── test_sanitizer.py
│   ├── test_security_fuzzing.py
│   ├── test_ssrf_protection.py
│   ├── test_task_queue.py
│   ├── test_tool_guard.py
│   ├── test_tool_guard_coverage.py
│   ├── test_upload_security.py
│   ├── test_upload_security_coverage.py
│   ├── test_xss_hardening.py
│   └── test_zero_trust.py
│
├── alembic/                        # ===== MIGRACIONES DE BD =====
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial_schema.py
│       └── 002_add_audit_log.py
│
├── deploy/                         # ===== CONFIGURACIÓN DE DESPLIEGUE =====
│   ├── nginx.conf                  # Reverse proxy para app + gateway + monitoring
│   ├── nginx-ssl.example.conf      # Configuración SSL de ejemplo
│   ├── grafana/provisioning/
│   │   └── datasources/prometheus.yml
│   ├── prometheus/
│   │   ├── prometheus.yml          # Configuración de scraping
│   │   └── alerts.yml              # Reglas de alertas
│   └── security/
│       ├── apparmor-sandbox.profile # Perfil AppArmor para sandbox
│       └── seccomp-sandbox.json    # Política Seccomp para sandbox
│
├── k8s/                            # ===== KUBERNETES =====
│   ├── README.md
│   ├── environments/
│   │   ├── production.yaml
│   │   └── staging.yaml
│   └── helm/superagente/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── _helpers.tpl
│           ├── configmap.yaml
│           ├── deployment-app.yaml
│           ├── deployment-monitoring.yaml
│           ├── deployment-worker.yaml
│           ├── hpa.yaml             # Horizontal Pod Autoscaler
│           ├── ingress.yaml
│           ├── namespace.yaml
│           ├── networkpolicy.yaml
│           ├── pdb.yaml             # Pod Disruption Budget
│           ├── podsecuritypolicy.yaml
│           ├── secret.yaml
│           ├── serviceaccount.yaml
│           ├── service-app.yaml
│           └── service-monitoring.yaml
│
├── translations/                   # ===== INTERNACIONALIZACIÓN =====
│   ├── es.json                     # Español
│   └── en.json                     # Inglés
│
├── static/
│   └── manifest.json               # PWA manifest
│
├── scripts/                        # ===== SCRIPTS AUXILIARES =====
│   ├── iniciar_agente.bat          # Lanzador Windows
│   ├── _build_estado_actual.py     # Generador de estado del proyecto
│   ├── manual_full_pipeline.py     # Pipeline manual de testing
│   ├── manual_pdfkit_probe.py      # Probe de pdfkit
│   ├── generate-sbom.sh            # Generación de SBOM (CycloneDX)
│   └── verify-image.sh             # Verificación de imagen Docker con Cosign
│
├── docs/                           # ===== DOCUMENTACIÓN =====
│   ├── ARCHITECTURE.md
│   ├── PRODUCTION_DEPLOY.md
│   ├── SECURITY_AUDIT.md
│   ├── DEAD_CODE_SCAN.md
│   ├── auditoria_post_refactor.md
│   └── PROJECT_STRUCTURE.md        # ← Este archivo
│
├── data/                           # Datos en runtime (BD SQLite, cuarentena)
├── generated_images/               # Imágenes y documentos generados
└── logs/                           # Logs de la aplicación
```

---

## 3. Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                        NGINX (Puerto 80)                     │
│                    Reverse Proxy + SSL                        │
└─────────┬──────────────────┬──────────────────┬─────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  Streamlit App  │ │   FastAPI    │ │   Monitoring     │
│   Puerto 8501   │ │   Gateway    │ │   API (8080)     │
│                 │ │  Puerto 8000 │ │                  │
│  ┌───────────┐  │ │  Zero-Trust  │ │  Prometheus      │
│  │    UI     │  │ │  Rate Limit  │ │  Metrics         │
│  │  Sidebar  │  │ │  Auth JWT    │ └──────────────────┘
│  │  Chat     │  │ └──────────────┘          │
│  │  Dialogs  │  │          │                ▼
│  └─────┬─────┘  │          │       ┌──────────────────┐
│        │        │          │       │   Prometheus     │
│  ┌─────▼─────┐  │          │       │   Puerto 9090    │
│  │  Runtime  │  │          │       └────────┬─────────┘
│  │  Engine   │  │          │                │
│  └─────┬─────┘  │          │                ▼
│        │        │          │       ┌──────────────────┐
│  ┌─────▼─────┐  │          │       │    Grafana       │
│  │ Services  │  │          │       │   Puerto 3000    │
│  │ LLM Prov. │  │          │       │   Dashboards     │
│  │ Security  │  │          │       └──────────────────┘
│  │ Tools     │  │          │
│  └─────┬─────┘  │          │
└────────┼────────┘          │
         │                   │
         ▼                   ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│   PostgreSQL    │ │    Redis     │ │   RQ Worker      │
│   Puerto 5432   │ │  Puerto 6379 │ │  Tareas Async    │
│                 │ │  Cache + Cola│ │                  │
│  · Usuarios     │ │              │ │  · Emails        │
│  · Chats        │ └──────────────┘ │  · Background    │
│  · Mensajes     │                  │    Jobs          │
│  · API Keys     │                  └──────────────────┘
│  · Audit Log    │
│  · Usage Log    │
└─────────────────┘
```

---

## 4. Flujo de Datos Principal

```
Usuario → Streamlit UI → app.py
                            │
                ┌───────────┼────────────────────────┐
                ▼           ▼                        ▼
          Auth Gate    Sidebar Panel           Chat Runtime
          (Login/      (Motor, Rol,           (runtime.py)
           Registro)    Archivos)                  │
                            │              ┌───────┼───────┐
                            │              ▼       ▼       ▼
                            │         SemanticCache │  LLM Provider
                            │              │       │  (Gemini/Groq/
                            │              │       │   OpenRouter/
                            │              │       │   Custom)
                            │              ▼       ▼
                            │         Tool Parser (agent_tools.py)
                            │              │
                            │    ┌─────────┼─────────────┐
                            │    ▼         ▼             ▼
                            │ search_web  create_file  execute_code
                            │    │         │             │
                            │    ▼         ▼             ▼
                            │ DuckDuckGo  FileFactory  Sandbox
                            │    │         │             │
                            │    ▼         ▼             ▼
                            └──── Respuesta renderizada en chat
```

---

## 5. Módulos Principales — Detalle

### 5.1 `app.py` — Punto de Entrada (180 líneas)

Orquesta el flujo completo de la aplicación:
1. Inicializa observabilidad (Sentry + OpenTelemetry)
2. Bootstrap: BD, directorios, garbage collection
3. Gestión de sesión: cookies, idle timeout, auto-login
4. Inyecta CSS global y meta PWA
5. Auth gate → Onboarding gate
6. Compone sidebar: perfil + menú + gestión de chats
7. Renderiza header, panel principal, mensajes y runtime de chat

### 5.2 `src/core/` — Núcleo

| Archivo | Responsabilidad |
|---|---|
| `config.py` | CSS global (~600 líneas), system prompts (PROMPT_TECH_LEAD, PROMPT_APP_BUILDER, PROMPT_UI_DESIGNER), constantes de rutas |
| `agent_tools.py` | Extrae bloques JSON de tool calls del texto LLM, valida con ToolGuard, sanitiza strings |
| `security.py` | Hash bcrypt, generación/verificación de tokens JWT, cifrado simétrico Fernet |
| `sanitizer.py` | Limpia Markdown con bleach contra XSS |
| `bootstrap.py` | Crea tablas BD, directorios, inicializa session_state, configura GC |
| `session_manager.py` | Cookie manager (extra-streamlit-components), idle timeout de 30 min, auto-login por remember token |
| `i18n.py` | Función `t(key)` para traducciones, carga JSON de `translations/` |
| `http_resilience.py` | Decorador de reintentos con backoff exponencial y circuit breaker |
| `observability.py` | Inicializa Sentry SDK + OpenTelemetry con exportador OTLP |

### 5.3 `src/database/database.py` — Persistencia (751 líneas)

Motor dual SQLite (desarrollo) / PostgreSQL (producción) vía SQLAlchemy Core.

**Tablas principales:**
- `users` — Registro, login, roles, verificación
- `api_keys` — Claves cifradas con Fernet por usuario
- `chats` — Conversaciones con título y timestamps
- `messages` — Mensajes append-only con `created_at`
- `usage_log` — Registro de consumo de tokens por proveedor
- `audit_log` — Log inmutable de eventos de seguridad
- `remember_tokens` — Tokens de sesión persistente
- `contact_messages` — Mensajes del formulario de contacto

**Funciones clave:**
- `register_user()`, `verify_login()`, `is_user_admin()`
- `create_chat()`, `get_user_chats()`, `delete_chat()`, `update_chat_title()`
- `save_chat_messages()` (append-only), `load_chat_messages()`, `search_chat_messages()`
- `update_api_keys()`, `get_user_api_keys()` (cifrado Fernet)
- `persist_usage_entry()`, `get_user_usage_summary()`

### 5.4 `src/services/llm_provider.py` — Proveedores LLM (503 líneas)

Patrón Wrapper/Adapter para desacoplar la UI de los SDKs de cada proveedor.

| Clase | Modelo | Características |
|---|---|---|
| `GeminiProvider` | gemini-2.5-pro | Multimodal (texto+imagen+video), streaming, continuation rounds |
| `GroqProvider` | llama-3.3-70b-versatile | Prompt compacto para TPM, auto-trim de historial, fallback a 8b-instant |
| `OpenRouterProvider` | openrouter/auto | Acceso a 100+ modelos, failover automático |
| `OllamaProvider` | llama3.1 (local) | Compatible con LM Studio, validación SSRF de URL |
| `CustomOpenAIProvider` | Cualquier endpoint OpenAI-compatible | Sin límite de max_tokens por defecto, validación SSRF |
| `LLMFactory` | — | Factoría centralizada `get_provider(motor_name, api_keys)` |

**Proveedores de audio:**
- `GroqWhisperProvider` — Transcripción STT con Whisper v3
- `OpenAITTSProvider` — Síntesis de voz (6 voces)
- `EdgeTTSProvider` — TTS gratuito con Microsoft Edge

### 5.5 `src/ui/chat/runtime.py` — Motor de Chat (355 líneas)

Función principal: `handle_chat_interaction()`

Flujo por iteración:
1. Recibe prompt del usuario + archivo adjunto opcional
2. Consulta caché semántica → si hit, devuelve directamente
3. Construye carga útil (texto + imagen/video para Gemini)
4. Llama al proveedor LLM con streaming
5. Si Groq falla → muestra error real → fallback a Gemini
6. Parsea tool calls del texto (`parse_tool_calls`)
7. Ejecuta herramientas: `search_web`, `create_file`, `execute_code`, `query_rag`, `open_converter`
8. Guarda en caché semántica + persiste en BD
9. Auto-titula el chat si es el primer mensaje

### 5.6 `src/security/` — Capa de Seguridad

| Módulo | Función |
|---|---|
| `zero_trust.py` | Middleware FastAPI: JWT auth, rate limiting por IP/usuario, HSTS headers |
| `ai_firewall.py` | Detecta y bloquea ataques adversariales a LLMs (prompt injection, jailbreak) |
| `prompt_injection_detector.py` | Heurísticas + patrones regex para detectar inyecciones en prompts |
| `tool_guard.py` | Whitelist de herramientas permitidas, control de permisos por rol |
| `url_validator.py` | Anti-SSRF: bloquea IPs privadas, loopback, metadata endpoints cloud |
| `path_guard.py` | Anti path traversal: normalización y validación de rutas de archivo |
| `policy_engine.py` | Motor de políticas configurable (RBAC, rate limits, restricciones por recurso) |
| `secrets_manager.py` | Gestión segura de secretos con cifrado AES, rotación automática |
| `llm_firewall.py` | Filtrado de salidas LLM: bloquea código malicioso, datos sensibles |

### 5.7 `src/services/file_factory.py` — Generación de Documentos (529 líneas)

Genera archivos a partir de instrucciones del LLM:
- **PDF**: HTML→PDF vía pdfkit/wkhtmltopdf con diseño profesional
- **HTML**: Archivos web completos con CSS embebido
- **Excel**: Tablas formateadas con openpyxl
- **Markdown**: Documentos .md

Incluye guardias de layout, fallback si pdfkit no está instalado, y validación del contenido generado.

### 5.8 `src/services/execution_sandbox.py` — Sandbox de Código (146 líneas)

Ejecución segura de código Python generado por el LLM:
- Proceso aislado con `subprocess`
- Timeout configurable
- Whitelist de imports permitidos
- Captura stdout/stderr
- Opcionalmente contenedor Docker con AppArmor + Seccomp

---

## 6. Infraestructura Docker

### `docker-compose.yml` — 8 servicios

| Servicio | Imagen | Puerto | Rol |
|---|---|---|---|
| `app` | Build local | 8501 | Aplicación Streamlit principal |
| `postgres` | postgres:16-alpine | 5432 | Base de datos relacional |
| `redis` | redis:7-alpine | 6379 | Cache + cola de mensajes |
| `worker` | Build local | — | RQ worker para tareas async |
| `gateway` | Build local | 8000 | API Gateway FastAPI |
| `monitoring` | Build local | 8080 | API de métricas Prometheus |
| `prometheus` | prom/prometheus:v2.53.0 | 9090 | Recolector de métricas |
| `grafana` | grafana/grafana:11.1.0 | 3000 | Dashboards de monitorización |
| `nginx` | nginx:1.27-alpine | 80 | Reverse proxy |

### Dockerfile — Multi-stage

- **Stage 1 (builder)**: Python 3.11-slim, compila dependencias con gcc
- **Stage 2 (runtime)**: Imagen mínima sin pip/gcc, usuario no-root `appuser`, healthcheck

---

## 7. CI/CD Pipeline

### `.github/workflows/ci.yml`

| Job | Herramienta | Propósito |
|---|---|---|
| `test` | pytest + Playwright | Tests unitarios + e2e |
| `dependency-audit` | pip-audit | Vulnerabilidades en dependencias |
| `dead-code` | Vulture (90%) | Detección de código muerto |
| `security-sast` | Bandit | Análisis estático de seguridad |
| `secret-scan` | Gitleaks | Detección de secretos en código |
| `docker-security` | Trivy | Vulnerabilidades en imagen Docker |

### `.github/workflows/supply-chain.yml`

- Generación de SBOM (Software Bill of Materials) con CycloneDX
- Firma de imagen Docker con Cosign
- Verificación de integridad

---

## 8. Kubernetes

Chart Helm completo en `k8s/helm/superagente/`:

- **Deployments**: app (2 réplicas), worker, monitoring
- **HPA**: Auto-escalado basado en CPU/memoria
- **PDB**: Pod Disruption Budget para alta disponibilidad
- **NetworkPolicy**: Aislamiento de red entre servicios
- **Ingress**: TLS con cert-manager
- **PodSecurityPolicy**: Restricciones de seguridad del pod
- **Entornos**: staging + production con values diferenciados

---

## 9. Dependencias Principales

| Paquete | Versión | Uso |
|---|---|---|
| `streamlit` | ≥1.30.0 | Framework UI principal |
| `google-genai` | latest | SDK de Google Gemini |
| `groq` | latest | SDK de Groq (Llama) |
| `openai` | latest | SDK OpenAI-compatible (OpenRouter, Custom, TTS) |
| `SQLAlchemy` | ≥2.0.0 | ORM / Core para BD |
| `psycopg2-binary` | ≥2.9.0 | Driver PostgreSQL |
| `redis` | ≥5.0.0 | Cache + cola |
| `fastapi` | ≥0.115.0 | API Gateway |
| `pydantic` | ≥2.0.0 | Validación de datos |
| `cryptography` | latest | Cifrado Fernet |
| `bcrypt` | latest | Hashing de contraseñas |
| `bleach` | ≥6.1.0 | Sanitización HTML/Markdown |
| `duckduckgo-search` | latest | Búsqueda web |
| `pdfkit` | latest | Generación de PDF |
| `Pillow` | latest | Procesamiento de imágenes |
| `edge-tts` | latest | TTS gratuito Microsoft |
| `prometheus-client` | ≥0.20.0 | Métricas de monitorización |
| `sentry-sdk` | ≥2.0.0 | Error tracking |
| `opentelemetry-*` | ≥1.20.0 | Distributed tracing |
| `alembic` | ≥1.13.0 | Migraciones de BD |
| `rq` | ≥1.16.0 | Cola de tareas Redis |

---

## 10. Variables de Entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `GEMINI_API_KEY` | Sí | Clave de Google Gemini |
| `GROQ_API_KEY` | No | Clave de Groq |
| `OPENROUTER_API_KEY` | No | Clave de OpenRouter |
| `OPENAI_API_KEY` | No | Clave de OpenAI (TTS) |
| `STABILITY_API_KEY` | No | Clave de Stability AI (imágenes) |
| `APP_SECRET_KEY` | Sí | Clave de cifrado de la aplicación |
| `DATABASE_URL` | No | URL PostgreSQL (fallback: SQLite) |
| `REDIS_URL` | No | URL de Redis |
| `SMTP_SERVER` | No | Servidor SMTP para emails |
| `SMTP_PORT` | No | Puerto SMTP |
| `SMTP_USER` | No | Usuario SMTP |
| `SMTP_PASSWORD` | No | Contraseña SMTP |
| `SMTP_FROM` | No | Dirección de remitente |
| `GROQ_MODEL` | No | Modelo preferido de Groq |
| `GROQ_FALLBACK_MODEL` | No | Modelo fallback de Groq |
| `GROQ_MAX_TOKENS` | No | Máx. tokens de respuesta Groq (default: 8000) |
| `GEMINI_MAX_TOKENS` | No | Máx. tokens Gemini (default: 65536) |
| `SENTRY_DSN` | No | DSN de Sentry para error tracking |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | Endpoint de OpenTelemetry |

---

## 11. Ejecución Local

```bash
# 1. Clonar y crear entorno virtual
git clone <repo-url>
cd "Agente de IA Local"
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus API keys

# 4. Ejecutar
streamlit run app.py
```

### Con Docker Compose (stack completo):

```bash
docker compose up --build -d
# App: http://localhost:80
# Grafana: http://localhost:3000
# Prometheus: http://localhost:9090
```

---

## 12. Tests

```bash
# Instalar dependencias de test
pip install -r requirements-dev.txt

# Ejecutar tests (sin e2e)
python -m pytest --ignore=tests/e2e

# Tests e2e (requiere Playwright)
python -m playwright install --with-deps chromium
python -m pytest tests/e2e/

# Tests de carga
pip install locust
locust -f tests/load/locustfile.py
```

**Suite de tests (30+ archivos):** seguridad, sandbox, XSS, SSRF, path traversal, prompt injection, compliance, gateway, observability, file validation, tool guard, chaos testing.

---

*Generado automáticamente — Mayo 2026*
