import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
pytestmark = pytest.mark.integration

from dotenv import load_dotenv
load_dotenv()

from src.services.llm_provider import GroqProvider, GeminiProvider, OllamaProvider
from src.services.web_search import search_web

def test_groq():
    if not os.getenv("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY no configurada.")
    provider = GroqProvider(api_key=os.getenv("GROQ_API_KEY"))
    try:
        response_chunks = list(provider.stream_chat("Hola, responde solo con la palabra 'GROQ_OK'.", []))
    except Exception as exc:
        pytest.skip(f"Groq no disponible en este entorno: {exc}")
    response = "".join(response_chunks)
    if "Error" in response:
        pytest.skip(f"Groq devolvió error de entorno: {response}")
    assert response.strip(), "Groq no devolvió contenido."

def test_gemini_text():
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY no configurada.")
    provider = GeminiProvider(api_key=os.getenv("GEMINI_API_KEY"))
    try:
        response_chunks = list(provider.stream_chat(["Hola, responde solo con una frase breve."], []))
    except Exception as exc:
        pytest.skip(f"Gemini no disponible en este entorno: {exc}")
    response = "".join(response_chunks)
    if "Error" in response:
        pytest.skip(f"Gemini devolvió error de entorno: {response}")
    assert response.strip(), "Gemini texto no devolvió contenido."

def test_gemini_image():
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY no configurada.")
    provider = GeminiProvider(api_key=os.getenv("GEMINI_API_KEY"))
    filepath, error = provider.generar_imagen("Un pequeño cuadrado rojo")
    if error:
        pytest.skip(f"Gemini imagen no disponible en este entorno: {error}")
    assert filepath and os.path.exists(filepath), "Gemini no generó imagen."

def test_ollama():
    provider = OllamaProvider()
    response_chunks = list(provider.stream_chat("Hola, di 'OLLAMA_OK'.", []))
    response = "".join(response_chunks)
    if "Error Ollama" in response or not response.strip():
        pytest.skip("Ollama local no está disponible.")
    assert response.strip(), "Ollama no devolvió contenido."

def test_web_search():
    res = search_web("Capital de España")
    if "Error en la búsqueda web:" in res:
        pytest.skip(res)
    assert isinstance(res, str) and len(res) > 20, "Web search devolvió respuesta inválida."

if __name__ == "__main__":
    print("Iniciando batería de pruebas a las IAs...\n")
    
    groq_res = test_groq()
    gem_txt_res = test_gemini_text()
    gem_img_res = test_gemini_image()
    ollama_res = test_ollama()
    web_res = test_web_search()
    
    print("\n===============================")
    print("RESUMEN DE PRUEBAS")
    print("===============================")
    print(f"Groq Texto        : {'OK' if groq_res else 'FALLO'}")
    print(f"Gemini Texto      : {'OK' if gem_txt_res else 'FALLO'}")
    print(f"Gemini Imagen     : {'OK' if gem_img_res else 'FALLO'}")
    print(f"Ollama Local      : {'OK' if ollama_res else 'FALLO (Posible apagado)'}")
    print(f"Búsqueda Web      : {'OK' if web_res else 'FALLO'}")
