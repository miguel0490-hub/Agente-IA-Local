"""Locust load testing configuration for SuperAgente IA Pro.

Run with: locust -f tests/load/locustfile.py --host http://localhost:8501
"""

from locust import HttpUser, task, between


class WebUser(HttpUser):
    """Simulates a typical user interacting with the Streamlit app."""

    wait_time = between(1, 5)

    @task(3)
    def load_homepage(self):
        self.client.get("/", name="Homepage")

    @task(1)
    def health_check(self):
        self.client.get("/_stcore/health", name="Health Check")

    @task(2)
    def load_static_assets(self):
        self.client.get("/_stcore/allowed-message-origins", name="Static Assets")
