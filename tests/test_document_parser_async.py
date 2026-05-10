from src.services import document_parser


class DummyFile:
    def __init__(self, content: str, name: str = "big.txt"):
        self._raw = content.encode("utf-8")
        self.name = name

    def read(self):
        return self._raw


def test_large_file_is_enqueued_when_async_available(monkeypatch):
    huge = "palabra " * 6001
    file_obj = DummyFile(huge, name="big.txt")
    monkeypatch.setattr(document_parser, "_EXTRACTORS", {".txt": lambda f: huge})
    monkeypatch.setattr(document_parser, "_VIDEO_EXTENSIONS", set())
    monkeypatch.setattr("src.services.task_queue.enqueue_rag_indexing", lambda n, c: "job-777")

    out = document_parser.extraer_texto_archivo(file_obj)
    assert "ENCOLADO EN CEREBRO RAG" in out
    assert "job-777" in out
