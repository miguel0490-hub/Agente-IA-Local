# Few-Shot: File Generation

## Ejemplo 1
**Usuario:** Genera un informe PDF sobre las ventajas de Python vs JavaScript.

**Asistente:**
```json
{
  "action": "create_file",
  "filename": "informe_python_vs_javascript.pdf",
  "content": "<!DOCTYPE html><html lang='es'><head>..."
}
```

## Ejemplo 2
**Usuario:** ¿Cuáles son las ventajas de Python vs JavaScript?

**Asistente:** (Responde en texto plano, SIN crear archivo porque no se pidió explícitamente)

Python y JavaScript tienen ventajas complementarias:
- **Python**: Sintaxis limpia, ciencia de datos, ML/AI, scripting...
- **JavaScript**: Dominio del navegador, ecosistema npm, full-stack con Node...
