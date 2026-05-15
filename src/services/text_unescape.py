"""Normaliza texto de herramientas LLM (create_file) con escapes literales."""

from __future__ import annotations


def unescape_llm_file_content(content: str) -> str:
    """Convierte ``\\n`` literales y artefactos JSON en texto listo para guardar."""
    if not content:
        return content

    text = content.strip()
    # Cierre de JSON pegado al final del campo (común en extracción tolerante)
    while text.endswith('"') or text.endswith("'"):
        text = text[:-1].rstrip()
    if text.endswith("\\n"):
        text = text[:-2].rstrip()

    # Secuencias escapadas que el modelo a veces deja como texto literal
    if "\\n" in text or "\\t" in text or '\\"' in text:
        text = (
            text.replace("\\r\\n", "\n")
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\'", "'")
        )

    text = text.strip()
    while text.endswith('"') or text.endswith("'"):
        text = text[:-1].rstrip()

    return text


def looks_like_escaped_markup(content: str) -> bool:
    """Detecta HTML/CSS/JS guardado como escapes literales en lugar de código real."""
    if not content or "\\n" not in content:
        return False
    lower = content.lower()
    if any(tag in lower for tag in ("<!doctype", "<html", "<head", "<body", ":root", "function ", "const ")):
        return content.count("\\n") > max(2, content.count("\n") * 2)
    return False
