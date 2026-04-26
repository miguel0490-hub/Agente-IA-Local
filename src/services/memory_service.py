import os
import json
from src.core.config import ARCHIVO_MEMORIA

def cargar_memoria() -> list:
    """Carga el historial de chat desde el archivo JSON."""
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f: 
                return json.load(f)
        except Exception as e: 
            print(f"Error cargando memoria: {e}")
            return []
    return []

def guardar_memoria(mensajes: list):
    """Guarda el historial de chat en el archivo JSON."""
    with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(mensajes, f, indent=4, ensure_ascii=False)

def limpiar_memoria():
    """Borra el archivo de memoria del sistema."""
    if os.path.exists(ARCHIVO_MEMORIA):
        os.remove(ARCHIVO_MEMORIA)
