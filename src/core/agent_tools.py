import json
import re
from pydantic import BaseModel, ValidationError
from typing import Optional
from src.core.logger import get_logger

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
    ALLOWED_ACTIONS = {"create_file", "edit_file", "search_web", "open_converter", "query_rag"}

    @staticmethod
    def authorize(tool_data: dict) -> Optional[dict]:
        try:
            validated = ToolCallModel(**tool_data)
            if validated.action not in ToolValidator.ALLOWED_ACTIONS:
                logger.warning(f"[SECURITY] Acción bloqueada por no estar en Allowlist: {validated.action}")
                return None
            return validated.model_dump(exclude_none=True)
        except ValidationError as e:
            logger.error(f"[VALIDATION ERROR] JSON no cumple el esquema: {e}")
            return None


def parse_tool_calls(text: str) -> tuple[str, list]:
    """Extrae llamadas a herramientas usando JSON estricto."""
    tools_to_run = []
    clean_text = text

    pattern = r"```json\s*([\s\S]*?)```"
    matches = list(re.finditer(pattern, text))

    for match in matches:
        raw_block = match.group(1).strip()
        raw_block = raw_block.replace("\n", "\\n").replace("\\\\n", "\\n")
        
        try:
            data = json.loads(raw_block, strict=False)
            # Si no es objeto JSON, no lo tratamos como tool-call y se conserva intacto.
            if not isinstance(data, dict):
                continue

            # Solo intentamos autorización cuando hay intención explícita de tool-call.
            if "action" not in data:
                continue

            authorized_tool = ToolValidator.authorize(data)

            if authorized_tool:
                tools_to_run.append(authorized_tool)
                action = authorized_tool.get("action")
                if action == "search_web":
                    aviso = f"\n> 🌐 **Búsqueda Web Autorizada:** `{authorized_tool.get('query', '')}`\n"
                else:
                    aviso = f"\n> 🛠️ **Herramienta Autorizada:** `{action}`\n"
                clean_text = clean_text.replace(match.group(0), aviso)
            else:
                # Si fue rechazado por permisos/validación, mantenemos el contenido original
                # para no ocultar información útil del chat.
                continue
        except json.JSONDecodeError:
            # No sobrescribir JSON informativo o ejemplos malformados del modelo.
            continue

    return clean_text, tools_to_run
