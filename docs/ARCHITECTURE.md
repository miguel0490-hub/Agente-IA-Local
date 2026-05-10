# Arquitectura del proyecto

## Visión general

| Capa | Rol |
|------|-----|
| **`app.py`** | Punto de entrada Streamlit: sesión, cookies, composición de UI y orquestación. |
| **`src/core/`** | Configuración, seguridad (rate limits, contexto HTTP), observabilidad, estado de sesión, herramientas del agente. |
| **`src/database/`** | Persistencia SQLite (usuarios, chats, tokens). |
| **`src/services/`** | Integraciones LLM, RAG, ficheros, cola RQ, parsing, conversiones. |
| **`src/security/`** | Detección de abuso en prompts y políticas de herramientas. |
| **`src/ui/`** | Componentes de interfaz por área (chat, sidebar, auth, multimedia, ajustes). |
| **`src/monitoring/`** | API FastAPI mínima para salud y métricas Prometheus (consumo interno / proxy). |

Flujo típico de chat: `app.py` → `ui/chat/runtime.py` → proveedor LLM (`services/`) → opcionalmente `agent_tools` / sandbox / RAG.

## Estructura de directorios

```
Agente de IA Local/
├── app.py                 # Entrada Streamlit
├── requirements.txt
├── requirements-dev.txt    # Opcional: vulture + pin a requirements.txt
├── Dockerfile
├── docker-compose.yml
├── deploy/
│   ├── nginx.conf              # Reverse proxy HTTP (Compose)
│   └── nginx-ssl.example.conf  # Plantilla TLS/HSTS (producción)
├── docs/                  # Documentación técnica y auditorías
├── tests/                 # Pytest (unitarios; e2e/integration marcados)
├── src/
│   ├── core/              # Config, seguridad, logging, agent_tools…
│   ├── database/
│   ├── services/
│   ├── security/
│   ├── ui/
│   └── monitoring/
├── data/                  # SQLite, cuarentena (no versionar)
├── generated_images/      # Artefactos generados (no versionar en prod si es efímero)
└── logs/
```

## Convenciones de código

- **Imports:** preferir `from src.<paquete>.<módulo> import ...` desde la raíz del proyecto (donde está `app.py`).
- **Secretos:** nunca en código; usar variables de entorno documentadas en `.env.example`.
- **Comentarios:** docstrings en módulos públicos y en funciones no triviales; evitar comentarios que repiten el nombre de la función.
- **Tests:** nuevos módulos con lógica crítica deben añadirse a `pytest.ini` si el proyecto exige cobertura 100 % sobre la lista `--cov=`.

## Scripts auxiliares

Ficheros de diagnóstico manual (no son tests automatizados) viven en `scripts/` para no confundirse con `tests/`.

## Código muerto

Metodología y limpiezas aplicadas: `docs/DEAD_CODE_SCAN.md`.
