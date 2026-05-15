"""
src/services/rag_service.py — Servicio de Recuperación Aumentada (RAG).

Indexa documentos en una base de datos SQLite FTS5 y ejecuta búsquedas
de texto completo (BM25) para inyectar contexto relevante al LLM.
"""
import sqlite3
import os
import re

DB_PATH = "data/rag_brain.db"

class RAGService:
    """Servicio de Cerebro de Larga Duración basado en SQLite FTS5 para RAG local sin dependencias."""

    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._init_db()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> "RAGService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _init_db(self):
        """Crea la tabla virtual FTS5 si no existe (idempotente)."""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS documents USING fts5(
                filename, chunk_text
            )
        ''')
        self.conn.commit()

    def _chunk_text(self, text, chunk_size=500, overlap=50):
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks

    def index_document(self, filename: str, content: str) -> int:
        """Indexa un documento dividiéndolo en fragmentos. Retorna el número de fragmentos."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM documents WHERE filename = ?", (filename,))
        
        chunks = self._chunk_text(content)
        for chunk in chunks:
            cursor.execute("INSERT INTO documents (filename, chunk_text) VALUES (?, ?)", (filename, chunk))
        self.conn.commit()
        return len(chunks)

    def query(self, query: str, limit: int = 8) -> list:
        """Busca fragmentos relevantes usando BM25/MATCH con fallback a LIKE."""
        cursor = self.conn.cursor()
        clean_query = re.sub(r'[^\w\s]', ' ', query).strip()

        try:
            fts_query = " OR ".join([f"{word}*" for word in clean_query.split() if len(word) > 2])
            if not fts_query:
                fts_query = clean_query
            cursor.execute('''
                SELECT filename, chunk_text FROM documents
                WHERE documents MATCH ?
                ORDER BY rank LIMIT ?
            ''', (fts_query, limit))
            results = cursor.fetchall()
        except Exception:
            cursor.execute('''
                SELECT filename, chunk_text FROM documents
                WHERE chunk_text LIKE ?
                LIMIT ?
            ''', (f"%{clean_query}%", limit))
            results = cursor.fetchall()

        return [{"filename": row[0], "content": row[1]} for row in results]
