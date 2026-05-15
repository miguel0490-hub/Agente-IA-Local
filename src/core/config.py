"""Application constants and legacy configuration exports."""
import os
from dotenv import load_dotenv

load_dotenv()

APP_SECRET_KEY = os.getenv("APP_SECRET_KEY")
if not APP_SECRET_KEY:
    raise RuntimeError(
        "[CONFIG ERROR] APP_SECRET_KEY no está configurada. "
        "Genérala con: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())' "
        "y añádela a tus Secrets (Streamlit Cloud) o al archivo .env local."
    )

# Configuración General
PAGE_TITLE = "SuperAgente IA Pro"
PAGE_ICON = "⚡"
LAYOUT = "wide"

# Directorios y Archivos
ARCHIVO_MEMORIA = "data/historial_chat.json"
CARPETA_IMAGENES = "generated_images"

# Claves de API — Motores LLM existentes
CLAVE_GEMINI = os.getenv("GEMINI_API_KEY")
CLAVE_GROQ = os.getenv("GROQ_API_KEY")
CLAVE_OPENROUTER = os.getenv("OPENROUTER_API_KEY")

# Claves de API — Nuevas herramientas (Audio + Imagen)
CLAVE_OPENAI = os.getenv("OPENAI_API_KEY")
CLAVE_STABILITY = os.getenv("STABILITY_API_KEY")

# Estilos globales (`ESTILOS_CSS`) y tokens de tema: `src/ui/theme.py` (inyectados desde `app.py`).
