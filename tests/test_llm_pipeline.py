"""
Test de integración real con Groq para validar el pipeline LLM->tools->FileFactory.
Se salta automáticamente cuando el entorno no está preparado (sin clave/red/certificados).
"""
import os
import sys

import pytest
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from src.core.agent_tools import parse_tool_calls
from src.core.config import CLAVE_GROQ, INSTRUCCIONES_SISTEMA
from src.services.file_factory import FileFactory

PROMPT_TEST = (
    "Genera un documento PDF breve de análisis DAFO de una panadería. "
    "Solo necesito ver que el bloque JSON y el HTML se generan correctamente."
)
pytestmark = pytest.mark.integration


@pytest.mark.integration
def test_llm_pipeline_groq_real():
    if not CLAVE_GROQ:
        pytest.skip("GROQ_API_KEY no configurada en este entorno.")

    groq_module = pytest.importorskip("groq", reason="Dependencia 'groq' no instalada.")
    Groq = groq_module.Groq
    APIConnectionError = getattr(groq_module, "APIConnectionError", Exception)

    client = Groq(api_key=CLAVE_GROQ)
    messages = [
        {"role": "system", "content": INSTRUCCIONES_SISTEMA},
        {"role": "user", "content": PROMPT_TEST},
    ]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=4096,
            temperature=0.3,
        )
    except APIConnectionError as exc:
        pytest.skip(f"Conectividad/certificados Groq no disponibles: {exc}")
    except Exception as exc:
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            pytest.skip(f"Certificados TLS no disponibles para Groq: {exc}")
        raise

    full_response = response.choices[0].message.content or ""
    _, tools = parse_tool_calls(full_response)
    assert tools, "El LLM no devolvió un bloque de herramienta parseable."

    tool_call = tools[0]
    factory = FileFactory(output_dir=os.path.abspath("generated_images"))
    result = factory.execute_tool(tool_call)
    assert result is not None, "FileFactory devolvió None en integración real."
