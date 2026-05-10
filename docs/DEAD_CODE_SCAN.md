# Escaneo de código muerto (`src/`, `app.py`)

## Herramienta

Se usa **[vulture](https://github.com/jendrikseipp/vulture)** con umbrales de confianza variables. Muchos avisos son **falsos positivos** típicos en aplicaciones Streamlit/FastAPI/RQ:

| Patrón | Por qué ignorar |
|--------|------------------|
| Variables en `st.session_state` | Asignación dinámica; vulture no ve uso analítico. |
| Endpoints FastAPI (`health`, `metrics`) | Referenciados por el servidor ASGI, no por imports Python. |
| Tareas RQ (`index_document_task`, …) | Referenciadas por **string** en `task_queue`. |
| `check_rate_limit` | API pública usada en tests y compatibilidad. |
| Constantes exportadas en `config.py` | Uso vía imports por otros módulos o plantillas. |

## Cambios aplicados tras el escaneo

1. **`src/core/observability.py`**: segundo argumento de `_before_send` renombrado a `_hint` (parámetro exigido por Sentry, no usado en el cuerpo).
2. **`src/services/file_factory.py`**: eliminado import no usado `numbers` (openpyxl).
3. **`src/services/provider_factory.py`**: eliminadas **`get_groq_provider`** y **`get_openrouter_provider`** (no referenciadas en el repo; el chat usa `LLMFactory` / imports directos donde aplica).

## Módulos completos

No se eliminó ningún archivo de **`src/services`** ni **`src/ui`**: todos los módulos tienen al menos una referencia en aplicación, tests o importaciones dinámicas encadenadas.

Para repetir el análisis localmente (mismas dependencias que en CI):

```bash
pip install -r requirements-dev.txt
python -m vulture src app.py --min-confidence 90
```

En **GitHub Actions** el job `dead-code` ejecuta el mismo comando (`--min-confidence 90`). Si falla, revisa falsos positivos en la tabla superior o sube el umbral solo tras consenso del equipo.
