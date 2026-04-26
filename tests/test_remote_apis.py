import os
import sys
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from src.services.llm_provider import GroqProvider, GeminiProvider, OllamaProvider
from src.services.web_search import search_web

def test_groq():
    print("\n--- Probando Groq Llama 3.3 ---")
    try:
        provider = GroqProvider()
        response_chunks = list(provider.stream_chat("Hola, responde solo con la palabra 'GROQ_OK'.", []))
        response = "".join(response_chunks)
        print(f"Resultado: {response}")
        return "GROQ_OK" in response.upper()
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_gemini_text():
    print("\n--- Probando Gemini 3.1 Pro (Texto) ---")
    try:
        provider = GeminiProvider()
        response_chunks = list(provider.stream_chat(["Hola, responde solo con la palabra 'GEMINI_OK'."], []))
        response = "".join(response_chunks)
        print(f"Resultado: {response}")
        return "GEMINI_OK" in response.upper()
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_gemini_image():
    print("\n--- Probando Gemini (Generación de Imagen) ---")
    try:
        provider = GeminiProvider()
        filepath, error = provider.generar_imagen("Un pequeño cuadrado rojo")
        if error:
            print(f"Error esperado o límite: {error}")
            return False # Depending on quota, might fail but logic works
        print(f"Imagen guardada en: {filepath}")
        return os.path.exists(filepath)
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_ollama():
    print("\n--- Probando Ollama Local ---")
    try:
        provider = OllamaProvider()
        response_chunks = list(provider.stream_chat("Hola, di 'OLLAMA_OK'.", []))
        response = "".join(response_chunks)
        print(f"Resultado: {response}")
        return True
    except Exception as e:
        print(f"Error esperado si Ollama no está encendido: {e}")
        return False

def test_web_search():
    print("\n--- Probando Web Search ---")
    try:
        res = search_web("Capital de España")
        print(f"Resultado longitud: {len(res)}")
        return "Madrid" in res
    except Exception as e:
        print(f"Error: {e}")
        return False

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
