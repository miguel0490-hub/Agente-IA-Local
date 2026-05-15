from src.services import task_queue


def test_get_redis_connection_no_redis(monkeypatch):
    monkeypatch.setattr(task_queue, "redis", None)
    assert task_queue._get_redis_connection() is None


def test_get_redis_connection_no_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "")
    class DummyRedis:
        @staticmethod
        def from_url(*args, **kwargs):
            raise AssertionError("should not be called")
    monkeypatch.setattr(task_queue, "redis", DummyRedis)
    assert task_queue._get_redis_connection() is None


def test_get_redis_connection_ok(monkeypatch):
    class Conn:
        def ping(self):
            return True

    class DummyRedis:
        @staticmethod
        def from_url(*args, **kwargs):
            return Conn()

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(task_queue, "redis", DummyRedis)
    task_queue._redis_connection = None
    task_queue._redis_url_cached = None
    assert task_queue._get_redis_connection() is not None


def test_get_redis_connection_reuses_cached_connection(monkeypatch):
    calls = {"from_url": 0, "ping": 0}

    class Conn:
        def ping(self):
            calls["ping"] += 1
            return True

    class DummyRedis:
        @staticmethod
        def from_url(*args, **kwargs):
            calls["from_url"] += 1
            return Conn()

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(task_queue, "redis", DummyRedis)
    task_queue._redis_connection = None
    task_queue._redis_url_cached = None
    first = task_queue._get_redis_connection()
    second = task_queue._get_redis_connection()
    assert first is second
    assert calls["from_url"] == 1
    assert calls["ping"] >= 1


def test_get_redis_connection_stale_cache_reconnects(monkeypatch):
    state = {"fail_ping": False}

    class Conn:
        def ping(self):
            if state["fail_ping"]:
                raise ConnectionError("stale connection")
            return True

    class DummyRedis:
        @staticmethod
        def from_url(*args, **kwargs):
            return Conn()

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(task_queue, "redis", DummyRedis)
    task_queue._redis_connection = None
    task_queue._redis_url_cached = None
    assert task_queue._get_redis_connection() is not None
    state["fail_ping"] = True
    assert task_queue._get_redis_connection() is not None


def test_enqueue_rag_indexing_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_ASYNC_TASKS", "0")
    assert task_queue.enqueue_rag_indexing("f.txt", "x") is None


def test_enqueue_rag_indexing_without_queue(monkeypatch):
    monkeypatch.setenv("ENABLE_ASYNC_TASKS", "1")
    monkeypatch.setattr(task_queue, "Queue", None)
    assert task_queue.enqueue_rag_indexing("f.txt", "x") is None


def test_enqueue_rag_indexing_ok(monkeypatch):
    class DummyJob:
        id = "job-123"

    class DummyQueue:
        def __init__(self, *args, **kwargs):
            pass

        def enqueue(self, *args, **kwargs):
            return DummyJob()

    monkeypatch.setenv("ENABLE_ASYNC_TASKS", "1")
    monkeypatch.setenv("RQ_QUEUE_NAME", "superagente")
    monkeypatch.setattr(task_queue, "Queue", DummyQueue)
    monkeypatch.setattr(task_queue, "_get_redis_connection", lambda: object())
    assert task_queue.enqueue_rag_indexing("f.txt", "content") == "job-123"


def test_get_redis_connection_handles_exception(monkeypatch):
    task_queue._redis_connection = None
    class DummyRedis:
        @staticmethod
        def from_url(*args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(task_queue, "redis", DummyRedis)
    assert task_queue._get_redis_connection() is None


def test_enqueue_rag_indexing_without_connection(monkeypatch):
    class DummyQueue:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setenv("ENABLE_ASYNC_TASKS", "1")
    monkeypatch.setattr(task_queue, "Queue", DummyQueue)
    monkeypatch.setattr(task_queue, "_get_redis_connection", lambda: None)
    assert task_queue.enqueue_rag_indexing("f.txt", "content") is None


def test_enqueue_conversion_and_transcription_ok(monkeypatch):
    class DummyJob:
        def __init__(self, jid):
            self.id = jid

    class DummyQueue:
        def __init__(self, *args, **kwargs):
            pass

        def enqueue(self, task_path, *args, **kwargs):
            if "convert_file_task" in task_path:
                return DummyJob("job-conv")
            return DummyJob("job-stt")

    monkeypatch.setenv("ENABLE_ASYNC_TASKS", "1")
    monkeypatch.setattr(task_queue, "Queue", DummyQueue)
    monkeypatch.setattr(task_queue, "_get_redis_connection", lambda: object())
    assert task_queue.enqueue_conversion("in", "out") == "job-conv"
    assert task_queue.enqueue_transcription(b"a", "f.mp3", 7) == "job-stt"


def test_get_job_status_without_job_or_connection(monkeypatch):
    assert task_queue.get_job_status("")["status"] == "unknown"
    monkeypatch.setattr(task_queue, "Job", object())
    monkeypatch.setattr(task_queue, "_get_redis_connection", lambda: None)
    assert task_queue.get_job_status("x")["status"] == "unavailable"


def test_get_job_status_finished_failed_and_missing(monkeypatch):
    class DummyJob:
        def __init__(self, status, result=None, exc_info=None):
            self._status = status
            self.result = result
            self.exc_info = exc_info

        def get_status(self, refresh=True):
            return self._status

    class DummyJobApi:
        @staticmethod
        def fetch(job_id, connection=None):
            if job_id == "done":
                return DummyJob("finished", result={"ok": True})
            if job_id == "bad":
                return DummyJob("failed", exc_info="boom")
            return DummyJob("started")

    monkeypatch.setattr(task_queue, "Job", DummyJobApi)
    monkeypatch.setattr(task_queue, "_get_redis_connection", lambda: object())
    assert task_queue.get_job_status("done")["status"] == "finished"
    assert task_queue.get_job_status("bad")["status"] == "failed"
    assert task_queue.get_job_status("wait")["status"] == "started"


def test_get_job_status_fetch_exception(monkeypatch):
    class DummyJobApi:
        @staticmethod
        def fetch(job_id, connection=None):
            raise RuntimeError("missing")

    monkeypatch.setattr(task_queue, "Job", DummyJobApi)
    monkeypatch.setattr(task_queue, "_get_redis_connection", lambda: object())
    payload = task_queue.get_job_status("nope")
    assert payload["status"] == "missing"
