import json
import re
from pydantic import BaseModel, ValidationError
from typing import Optional
from src.core.logger import get_logger
from src.security.prompt_injection_detector import PromptInjectionDetector
from src.security.tool_guard import ToolGuard

logger = get_logger(__name__)


class ToolCallModel(BaseModel):
    """Esquema estricto de las herramientas permitidas."""
    action: str
    filename: Optional[str] = None
    content: Optional[str] = None
    search: Optional[str] = None
    replace: Optional[str] = None
    query: Optional[str] = None
    language: Optional[str] = None
    code: Optional[str] = None
    suggested_format: Optional[str] = None


class ToolValidator:
    """Capa de Autorización y Permisos (Tool Permission Layer)."""
    ALLOWED_ACTIONS = {"create_file", "edit_file", "search_web", "open_converter", "query_rag", "execute_code"}

    @staticmethod
    def authorize(tool_data: dict) -> Optional[dict]:
        try:
            validated = ToolCallModel(**tool_data)
            if validated.action not in ToolValidator.ALLOWED_ACTIONS:
                logger.warning(f"[SECURITY] Acción bloqueada por no estar en Allowlist: {validated.action}")
                return None
            as_dict = validated.model_dump(exclude_none=True)
            decision = ToolGuard.evaluate(validated.action)
            if not decision.allowed:
                logger.warning(f"[SECURITY] Acción bloqueada por política: {validated.action} ({decision.reason})")
                return None
            if decision.requires_confirmation:
                as_dict["requires_confirmation"] = True
            return as_dict
        except ValidationError as e:
            logger.error(f"[VALIDATION ERROR] JSON no cumple el esquema: {e}")
            return None


def _extract_balanced_json_objects(text: str) -> list[str]:
    """Extrae objetos JSON balanceados de texto libre, respetando comillas."""
    objects = []
    start = -1
    depth = 0
    in_string = False
    escaped = False

    for idx, ch in enumerate(text):
        if ch == "\\" and in_string and not escaped:
            escaped = True
            continue

        if ch == '"' and not escaped:
            in_string = not in_string
        escaped = False

        if in_string:
            continue

        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    objects.append(text[start : idx + 1])
                    start = -1

    return objects


def _extract_field(raw_block: str, field: str) -> Optional[str]:
    """Extrae un campo string incluso en JSON malformado por comillas internas."""
    marker = f'"{field}"'
    pos = raw_block.find(marker)
    if pos == -1:
        return None

    colon = raw_block.find(":", pos + len(marker))
    if colon == -1:
        return None

    i = colon + 1
    while i < len(raw_block) and raw_block[i].isspace():
        i += 1
    if i >= len(raw_block):
        return None

    if raw_block[i] == '"':
        i += 1
        start = i
        while i < len(raw_block):
            ch = raw_block[i]
            if ch == '"' and raw_block[i - 1] != "\\":
                tail = raw_block[i + 1 :]
                if tail.lstrip().startswith(",") or tail.lstrip().startswith("}"):
                    return raw_block[start:i]
            i += 1
        return raw_block[start:].rstrip("}")

    end = raw_block.find(",", i)
    if end == -1:
        end = raw_block.find("}", i)
    if end == -1:
        end = len(raw_block)
    return raw_block[i:end].strip().strip('"')


def _parse_tool_payload(raw_block: str) -> Optional[dict]:
    """Parsea tool-call desde JSON estricto o fallback tolerante."""
    try:
        data = json.loads(raw_block, strict=False)
        if isinstance(data, dict) and "action" in data:
            return data
    except json.JSONDecodeError:
        pass

    action = _extract_field(raw_block, "action")
    if not action:
        return None

    payload = {"action": action}
    for key in ("filename", "content", "search", "replace", "query", "language", "code", "suggested_format"):
        value = _extract_field(raw_block, key)
        if value is not None:
            payload[key] = value
    return payload


def parse_tool_calls(text: str) -> tuple[str, list]:
    """Extrae llamadas a herramientas usando JSON estricto."""
    tools_to_run = []
    clean_text = text

    pattern = r"```json\s*([\s\S]*?)```"
    matches = list(re.finditer(pattern, text))
    consumed_blocks = set()
    text_without_fences = re.sub(pattern, "", text)

    for match in matches:
        raw_block = match.group(1).strip()
        raw_block = raw_block.replace("\n", "\\n").replace("\\\\n", "\\n")
        consumed_blocks.add(raw_block)
        if PromptInjectionDetector.detect(raw_block):
            logger.warning("[SECURITY] Bloque JSON rechazado por patrón de prompt-injection.")
            continue

        data = _parse_tool_payload(raw_block)
        if not data:
            continue

        # Mensaje conversacional estructurado: no se ejecuta herramienta.
        if data.get("action") == "respond" and data.get("message"):
            clean_text = clean_text.replace(match.group(0), str(data.get("message")))
            continue

        authorized_tool = ToolValidator.authorize(data)
        if authorized_tool:
            tools_to_run.append(authorized_tool)
            action = authorized_tool.get("action")
            if action == "search_web":
                aviso = f"\n> 🌐 **Búsqueda Web Autorizada:** `{authorized_tool.get('query', '')}`\n"
            else:
                aviso = f"\n> 🛠️ **Herramienta Ejecutada:** `{action}`\n"
            clean_text = clean_text.replace(match.group(0), aviso)

    # Fallback para JSON crudo fuera de markdown fences.
    for raw_obj in _extract_balanced_json_objects(text_without_fences):
        candidate = raw_obj.strip()
        if PromptInjectionDetector.detect(candidate):
            continue
        data = _parse_tool_payload(candidate)
        if not data:
            continue
        if data.get("action") == "respond" and data.get("message"):
            clean_text = clean_text.replace(raw_obj, str(data.get("message")))
            continue
        authorized_tool = ToolValidator.authorize(data)
        if not authorized_tool:
            continue
        tools_to_run.append(authorized_tool)
        action = authorized_tool.get("action")
        if action == "search_web":
            aviso = f"\n> 🌐 **Búsqueda Web Autorizada:** `{authorized_tool.get('query', '')}`\n"
        else:
            aviso = f"\n> 🛠️ **Herramienta Ejecutada:** `{action}`\n"
        clean_text = clean_text.replace(raw_obj, aviso)

    # Limpia prefijos de rol residuales que algunos modelos inyectan (ej: "agt:", "assistant:").
    clean_text = re.sub(r"(?im)^\s*(agt|agent|assistant|asistente)\s*:\s*", "", clean_text)
    # Limpia variantes desconocidas justo antes de avisos de tool-call, tanto al inicio
    # de línea como inline (ej: "x7: 🛠️ Herramienta Ejecutada..." o "nota x7: > 🛠️ ...").
    clean_text = re.sub(
        r"(?im)^\s*[^:\n]{1,24}\s*:\s*(?=(?:>\s*)?(?:🛠️|🌐|Herramienta Ejecutada|Búsqueda Web Autorizada))",
        "",
        clean_text,
    )
    clean_text = re.sub(
        r"(?i)(?:^|\s)[^\s:\n]{1,24}\s*:\s*(?=(?:>\s*)?(?:🛠️|🌐|Herramienta Ejecutada|Búsqueda Web Autorizada))",
        " ",
        clean_text,
    ).strip()

    return clean_text, tools_to_run
