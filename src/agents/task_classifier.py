"""Task classifier — detects user intent to route to the right agent behavior."""

from __future__ import annotations

import re

_PATTERNS: dict[str, list[str]] = {
    "code_review": [r"revis[ae]", r"audit[ae]", r"analiz[ae]\s+(?:el\s+)?c[oó]digo", r"code\s*review"],
    "web_research": [r"busc[ae]", r"investig[ae]", r"search", r"qué\s+es", r"quién\s+es", r"cómo\s+funciona"],
    "file_generation": [r"(?:crea|genera|escribe|haz)\s+(?:un|el)\s+(?:pdf|archivo|documento|excel|html|informe|reporte)"],
    "code_generation": [r"(?:crea|genera|programa|escribe|desarrolla)\s+(?:un|una|el|la)\s+(?:app|aplicaci[oó]n|script|funci[oó]n|clase|componente|api)"],
    "security_scan": [r"seguridad", r"vulnerabilid", r"pentest", r"scan", r"exploit"],
    "devops": [r"docker", r"kubernetes", r"deploy", r"ci[\s/]cd", r"pipeline", r"nginx", r"monitor"],
    "design": [r"diseñ[oa]", r"css", r"layout", r"responsive", r"ui[\s/]?ux", r"frontend", r"interfaz"],
    "data_analysis": [r"anali[sz][ae]", r"datos", r"estadístic", r"csv", r"excel", r"gráfic"],
    "multimedia": [r"imagen", r"audio", r"video", r"convert", r"transcri"],
    "general": [],
}

_COMPILED: dict[str, list[re.Pattern]] = {
    task: [re.compile(p, re.IGNORECASE) for p in patterns]
    for task, patterns in _PATTERNS.items()
}


_TASK_CONTEXTS: dict[str, str] = {
    "code_review": "Analiza el código línea por línea. Busca bugs, malas prácticas, vulnerabilidades y oportunidades de mejora. Sé específico con las correcciones.",
    "web_research": "Busca información actualizada. Sintetiza las fuentes en un resumen claro y estructurado. Cita las fuentes cuando sea posible.",
    "file_generation": "Genera el documento con formato profesional, estructura clara y contenido completo. Solo genera archivos cuando el usuario lo pida explícitamente.",
    "code_generation": "Escribe código limpio, bien documentado y con manejo de errores. Sigue los patrones del proyecto existente.",
    "security_scan": "Revisa sistemáticamente: inyección, autenticación, autorización, criptografía, configuración, y exposición de datos. Prioriza por severidad.",
    "devops": "Sigue mejores prácticas de infraestructura como código. Incluye health checks, logs, y monitorización.",
    "design": "Prioriza accesibilidad, responsive design, y rendimiento. Usa el sistema de diseño existente del proyecto.",
    "data_analysis": "Analiza los datos de forma rigurosa. Presenta conclusiones con evidencia y visualizaciones cuando sea posible.",
    "multimedia": "Gestiona archivos multimedia de forma eficiente. Valida formatos y tamaños antes de procesar.",
    "debugging": "El usuario tiene un bug. Analiza paso a paso, identifica la causa raíz y propón corrección.",
}


def classify_task(prompt: str) -> str:
    """Returns the most likely task type from the user's prompt."""
    scores: dict[str, int] = {}
    for task_type, patterns in _COMPILED.items():
        score = sum(1 for p in patterns if p.search(prompt))
        if score > 0:
            scores[task_type] = score

    if not scores:
        return "general"
    return max(scores, key=scores.get)


def get_task_context(task_type: str) -> str:
    """Returns additional context instructions based on classified task type."""
    return _TASK_CONTEXTS.get(task_type, "")
