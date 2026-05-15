"""RQ background task handlers."""

from __future__ import annotations

import os

from src.database.database import get_user_api_keys
from src.services.audio_service import transcribe_audio_with_groq
from src.services.converter_service import run_conversion
from src.services.rag_service import RAGService


def index_document_task(filename: str, content: str) -> int:
    """Indexes a large document in the RAG store and returns chunk count."""
    rag = RAGService()
    try:
        return rag.index_document(filename, content)
    finally:
        rag.close()


def convert_file_task(input_path: str, output_path: str) -> dict:
    """Converts a file and returns a serializable result payload."""
    ok = run_conversion(input_path, output_path)
    return {"ok": bool(ok), "output_path": output_path}


def transcribe_audio_task(audio_bytes: bytes, filename: str, user_id: int) -> dict:
    """Runs STT and returns transcript payload (clave GROQ desde BD o env, no por la cola)."""
    if not user_id:
        return {"ok": False, "text": "", "error": "Usuario no válido para transcripción."}
    keys = get_user_api_keys(int(user_id)) or {}
    api_key = (keys.get("GROQ_API_KEY") or "").strip() or os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "text": "", "error": "Sin clave GROQ configurada para este usuario."}
    text, error = transcribe_audio_with_groq(audio_bytes, api_key, filename)
    return {"ok": error is None, "text": text, "error": error}
