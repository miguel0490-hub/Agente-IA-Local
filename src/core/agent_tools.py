import json
import re


def parse_tool_calls(text: str) -> tuple[str, list]:
    """
    Busca bloques JSON marcados como llamadas a herramientas en el texto del LLM.
    Retorna el texto limpio (sin los bloques JSON) y la lista de herramientas a ejecutar.

    ARQUITECTURA DEL PARSER (por capas, del más estricto al más permisivo):
      1. json.loads() estándar
      2. Sanitización de control chars + json.loads()
      3. Extracción manual robusta (para HTML con {}, comillas y \\n reales)
    """
    tools_to_run = []
    clean_text = text

    # Captura TODO entre ```json y ``` (incluyendo {} del CSS y saltos de línea)
    pattern = r"```json\s*([\s\S]*?)```"
    matches = list(re.finditer(pattern, text))

    for match in matches:
        raw_block = match.group(1).strip()
        data = _robust_parse(raw_block)

        if not data:
            continue
        action = data.get("action")
        if action not in ("create_file", "edit_file", "search_web", "open_converter"):
            continue

        # Limpiar la clave interna de diagnóstico antes de almacenar
        data.pop("_recovered", None)
        tools_to_run.append(data)
        if action == "search_web":
            aviso = f"\n> 🌐 **Búsqueda Web Solicitada:** `{data.get('query', '')}`\n"
        else:
            aviso = (
                f"\n> 🛠️ **Herramienta Ejecutada:** "
                f"`{action}` en `{data.get('filename', 'archivo')}`\n"
            )
        clean_text = clean_text.replace(match.group(0), aviso)

    # ── CAPA 2: Fallback para JSON sin fences (cuando el LLM omite las marcas) ──
    if not tools_to_run:
        # Intentamos extraer lo que haya entre la primera { y la última } que contenga una action válida
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            raw_block = text[first_brace:last_brace+1]
            # Verificamos que parezca una tool antes de intentar el parseo pesado
            if '"action"' in raw_block and any(a in raw_block for a in ("create_file", "edit_file", "search_web", "open_converter")):
                data = _robust_parse(raw_block)
                if data:
                    action = data.get("action")
                    if action in ("create_file", "edit_file", "search_web", "open_converter"):
                        data.pop("_recovered", None)
                        tools_to_run.append(data)
                        if action == "search_web":
                            aviso = f"\n> 🌐 **Búsqueda Web Solicitada:** `{data.get('query', '')}`\n"
                        else:
                            aviso = (
                                f"\n> 🛠️ **Herramienta Ejecutada:** "
                                f"`{action}` en `{data.get('filename', 'archivo')}`\n"
                            )
                        clean_text = clean_text.replace(raw_block, aviso)

    return clean_text, tools_to_run


# ─────────────────────────────────────────────────────────────────────────────
# Capas del parser
# ─────────────────────────────────────────────────────────────────────────────

def _robust_parse(json_str: str) -> dict | None:
    """Intenta parsear el bloque JSON por tres métodos en cascada."""

    # Capa 1: JSON estándar (caso feliz)
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        pass

    # Capa 2: Sanitizar caracteres de control dentro de strings y reintentar.
    # El LLM introduce saltos de línea REALES dentro de los valores string del JSON
    # (e.g. el HTML en "content"), lo cual es inválido en JSON estricto.
    try:
        sanitized = _sanitize_json_control_chars(json_str)
        return json.loads(sanitized)
    except (json.JSONDecodeError, ValueError):
        pass

    # Capa 3: Extracción manual. Usada cuando el HTML tiene caracteres que
    # rompen incluso la sanitización (comillas no escapadas, etc.)
    return _manual_extract(json_str)


def _sanitize_json_control_chars(json_str: str) -> str:
    """
    Recorre el JSON carácter a carácter y escapa los caracteres de control
    (\\n, \\r, \\t reales) que aparezcan DENTRO de un string JSON.
    Respeta las comillas escapadas (\\\") para no confundirlas con delimitadores.
    """
    result = []
    in_string = False
    i = 0
    n = len(json_str)

    while i < n:
        ch = json_str[i]

        # Detectar entrada/salida de string (respetando escapes)
        if ch == '"' and (i == 0 or json_str[i - 1] != "\\"):
            in_string = not in_string
            result.append(ch)
        elif in_string:
            if ch == "\n":
                result.append("\\n")
            elif ch == "\r":
                result.append("\\r")
            elif ch == "\t":
                result.append("\\t")
            else:
                result.append(ch)
        else:
            result.append(ch)
        i += 1

    return "".join(result)


def _manual_extract(json_str: str) -> dict | None:
    """
    Extracción de último recurso para JSON severamente malformado.
    Busca action y filename con regex simple, y extrae content como todo
    lo que hay entre la apertura de su string y el último '\"' antes del
    cierre del objeto JSON. Funciona con HTML que tiene {}, comillas, etc.
    """
    action_m   = re.search(r'"action"\s*:\s*"([^"]+)"',   json_str)
    filename_m = re.search(r'"filename"\s*:\s*"([^"]+)"', json_str)

    if not action_m or not filename_m:
        return None

    # Localizar el inicio del valor de "content"
    content_key_pos = json_str.find('"content"')
    if content_key_pos == -1:
        return None

    after_key   = json_str[content_key_pos + len('"content"'):]
    colon_idx   = after_key.find(":")
    if colon_idx == -1:
        return None

    after_colon = after_key[colon_idx + 1:].lstrip()
    if not after_colon.startswith('"'):
        return None

    # El contenido empieza tras la primera comilla
    inner = after_colon[1:]
    
    # BUSQUEDA ROBUSTA DE LA COMILLA DE CIERRE:
    # Buscamos la última comilla que esté seguida opcionalmente de espacios y luego un } o un ,
    # Esto evita que comillas internas del HTML (si el LLM no las escapó) rompan la extracción.
    content_match = re.search(r'([\s\S]*?)"\s*[},]', inner)
    if not content_match:
        # Fallback: última comilla del bloque
        last_quote = inner.rfind('"')
        if last_quote == -1: return None
        raw_content = inner[:last_quote]
    else:
        raw_content = content_match.group(1)

    # Desescapar secuencias JSON estándar
    unescaped = (
        raw_content
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )

    return {
        "action":     action_m.group(1),
        "filename":   filename_m.group(1),
        "content":    unescaped,
        "_recovered": True,
    }
