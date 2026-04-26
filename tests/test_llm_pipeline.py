"""
Test definitivo: llama al LLM real (Groq) y captura exactamente lo que genera,
luego lo pasa por el parser y el FileFactory exactamente como lo hace agente.py.
"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from src.core.config import INSTRUCCIONES_SISTEMA, CLAVE_GROQ
from src.core.agent_tools import parse_tool_calls
from src.services.file_factory import FileFactory

PROMPT_TEST = (
    "Genera un documento PDF breve de análisis DAFO de una panadería. "
    "Solo necesito ver que el bloque JSON y el HTML se generan correctamente."
)

print("=" * 60)
print("TEST: Llamada real a Groq + pipeline completo")
print("=" * 60)

from groq import Groq
client = Groq(api_key=CLAVE_GROQ)

messages = [
    {"role": "system", "content": INSTRUCCIONES_SISTEMA},
    {"role": "user", "content": PROMPT_TEST}
]

print("Llamando a Groq Llama 3.3...")
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=messages,
    max_tokens=4096,
    temperature=0.3
)

full_response = response.choices[0].message.content
print(f"\nRespuesta del LLM ({len(full_response)} chars):")
print("--- PRIMEROS 500 chars ---")
print(full_response[:500])
print("--- ÚLTIMOS 200 chars ---")
print(full_response[-200:])

print("\n" + "=" * 60)
print("Pasando por parse_tool_calls...")
print("=" * 60)

clean, tools = parse_tool_calls(full_response)
print(f"Herramientas detectadas: {len(tools)}")

if tools:
    t = tools[0]
    print(f"action  : {t.get('action')}")
    print(f"filename: {t.get('filename')}")
    content = t.get('content', '')
    print(f"content len: {len(content)}")
    print(f"content[:100]: {repr(content[:100])}")
    print(f"Es HTML: {'<!doctype' in content.lower() or '<html' in content.lower()}")
    
    print("\n" + "=" * 60)
    print("Ejecutando FileFactory...")
    print("=" * 60)
    factory = FileFactory(output_dir=os.path.abspath('generated_images'))
    result = factory.execute_tool(t)
    if result:
        ext = os.path.splitext(result)[1]
        size = os.path.getsize(result) if os.path.exists(result) else 0
        print(f"Resultado: {result}")
        print(f"Extension: {ext} | Tamaño: {size} bytes")
        if ext == '.pdf':
            print("\n>>> PIPELINE COMPLETO: ÉXITO <<<")
        else:
            print(f"\n>>> FALLO: generó {ext} en lugar de .pdf <<<")
    else:
        print(">>> FALLO: FileFactory devolvió None <<<")
else:
    print(">>> FALLO: parse_tool_calls no detectó ninguna herramienta <<<")
    print("\nContenido completo de la respuesta del LLM para diagnóstico:")
    print(full_response)
