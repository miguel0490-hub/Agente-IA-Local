"""RQ background task handlers."""

from __future__ import annotations

from src.services.audio_service import transcribe_audio_with_groq
from src.services.converter_service import run_conversion
from src.services.rag_service import RAGService


def index_document_task(filename: str, content: str) -> int:
    """Indexes a large document in the RAG store and returns chunk count."""
    rag = RAGService()
    return rag.index_document(filename, content)


def convert_file_task(input_path: str, output_path: str) -> dict:
    """Converts a file and returns a serializable result payload."""
    ok = run_conversion(input_path, output_path)
    return {"ok": bool(ok), "output_path": output_path}


def transcribe_audio_task(audio_bytes: bytes, filename: str, api_key: str) -> dict:
    """Runs STT and returns transcript payload."""
    text, error = transcribe_audio_with_groq(audio_bytes, api_key, filename)
    return {"ok": error is None, "text": text, "error": error}
