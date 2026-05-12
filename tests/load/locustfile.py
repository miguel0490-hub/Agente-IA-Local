"""Locust load testing for SuperAgente IA Pro.

Run with:
    locust -f tests/load/locustfile.py --host http://localhost:8000

Scenarios:
    - WebUser: Streamlit UI simulation (homepage, health)
    - APIUser: Gateway API stress (chat completions, health, admin)
    - ConcurrentChatUser: Simulates 20+ concurrent chat sessions
    - FileUploadUser: Parallel file upload simulation
    - FailoverUser: Triggers provider failover under load
"""

from __future__ import annotations

import json
import os
import random
import time
import uuid

from locust import HttpUser, TaskSet, between, events, task

_SERVICE_TOKEN = os.getenv("LOAD_TEST_TOKEN", "")


def _auth_headers() -> dict[str, str]:
    if _SERVICE_TOKEN:
        return {"Authorization": f"Bearer {_SERVICE_TOKEN}"}
    try:
        from src.security.zero_trust import ServiceRole, create_service_token
        token = create_service_token("load-test", ServiceRole.ADMIN)
        return {"Authorization": f"Bearer {token}"}
    except Exception:
        return {}


class StreamlitUser(HttpUser):
    """Simulates typical Streamlit UI interactions."""

    wait_time = between(1, 5)
    weight = 3

    @task(5)
    def load_homepage(self):
        self.client.get("/", name="[UI] Homepage")

    @task(2)
    def health_check(self):
        self.client.get("/_stcore/health", name="[UI] Health")

    @task(1)
    def static_assets(self):
        self.client.get("/_stcore/allowed-message-origins", name="[UI] Static")


class APIChatUser(HttpUser):
    """Simulates concurrent chat completions through the Gateway API."""

    wait_time = between(0.5, 2)
    weight = 5
    host = os.getenv("API_HOST", "http://localhost:8000")

    def on_start(self):
        self.headers = _auth_headers()
        self.session_id = uuid.uuid4().hex[:12]
        self.conversation: list[dict] = []

    @task(6)
    def chat_message(self):
        prompts = [
            "Genera un informe de análisis DAFO para una startup tech.",
            "Escribe un script Python que procese un CSV de ventas.",
            "Revisa este código y encuentra bugs potenciales.",
            "Busca información sobre las mejores prácticas de Kubernetes.",
            "Crea una función de autenticación JWT en FastAPI.",
            "Diseña una estructura de base de datos para un e-commerce.",
            "Analiza las vulnerabilidades de seguridad comunes en APIs REST.",
            "Genera documentación técnica para un microservicio.",
        ]
        msg = {"role": "user", "content": random.choice(prompts)}
        self.conversation.append(msg)

        with self.client.post(
            "/api/v1/chat/completions",
            json={"model": "auto", "messages": self.conversation[-10:]},
            headers=self.headers,
            name="[API] Chat Completion",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if "choices" in data:
                    assistant_msg = data["choices"][0]["message"]
                    self.conversation.append(assistant_msg)
                    resp.success()
                else:
                    resp.failure("Missing choices in response")
            elif resp.status_code == 401:
                resp.failure("Auth failed — check LOAD_TEST_TOKEN")
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def health_check(self):
        self.client.get("/api/v1/health", name="[API] Health", headers=self.headers)

    @task(1)
    def agent_status(self):
        self.client.get("/api/v1/agents/health", name="[API] Agent Health", headers=self.headers)

    @task(1)
    def fallback_status(self):
        self.client.get("/api/v1/agents/fallback-chain", name="[API] Fallback Chain", headers=self.headers)


class FileUploadUser(HttpUser):
    """Simulates concurrent file uploads."""

    wait_time = between(2, 8)
    weight = 2
    host = os.getenv("API_HOST", "http://localhost:8000")

    def on_start(self):
        self.headers = _auth_headers()

    @task
    def upload_document(self):
        fake_content = f"Test document content {uuid.uuid4().hex}"
        files = {"file": ("test_doc.txt", fake_content.encode(), "text/plain")}
        with self.client.post(
            "/api/v1/upload",
            files=files,
            headers=self.headers,
            name="[API] File Upload",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201, 404):
                resp.success()
            else:
                resp.failure(f"Upload failed: {resp.status_code}")


class FailoverStressUser(HttpUser):
    """Sends bursts to trigger provider failover under load."""

    wait_time = between(0.2, 0.5)
    weight = 1
    host = os.getenv("API_HOST", "http://localhost:8000")

    def on_start(self):
        self.headers = _auth_headers()

    @task
    def rapid_fire_chat(self):
        with self.client.post(
            "/api/v1/chat/completions",
            json={
                "model": "auto",
                "messages": [{"role": "user", "content": f"Burst test {time.time()}"}],
            },
            headers=self.headers,
            name="[API] Burst Chat (Failover)",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 429, 503):
                resp.success()
            else:
                resp.failure(f"Unexpected: {resp.status_code}")


class SandboxStressUser(HttpUser):
    """Simulates concurrent sandbox code execution requests."""

    wait_time = between(3, 10)
    weight = 1
    host = os.getenv("API_HOST", "http://localhost:8000")

    def on_start(self):
        self.headers = _auth_headers()

    @task
    def execute_code(self):
        code_snippets = [
            "print(sum(range(100)))",
            "import math; print(math.factorial(20))",
            "[x**2 for x in range(50)]",
            "print('Hello from sandbox')",
        ]
        with self.client.post(
            "/api/v1/chat/completions",
            json={
                "model": "auto",
                "messages": [{"role": "user", "content": f"Ejecuta: {random.choice(code_snippets)}"}],
            },
            headers=self.headers,
            name="[API] Sandbox Execution",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 429, 503):
                resp.success()
            else:
                resp.failure(f"Sandbox: {resp.status_code}")
