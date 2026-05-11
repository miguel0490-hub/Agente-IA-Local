"""Tests for src/observability — tracing, AI metrics, alerting, and dashboards."""

from __future__ import annotations

import json
import pathlib
from unittest.mock import patch

import pytest

DASHBOARD_DIR = pathlib.Path(__file__).resolve().parent.parent / "src" / "observability" / "dashboards"


# ---------------------------------------------------------------------------
# Tracing
# ---------------------------------------------------------------------------
class TestTracing:
    def test_init_tracing_skips_without_endpoint(self):
        """init_tracing should be a no-op when OTEL_EXPORTER_OTLP_ENDPOINT is empty."""
        from src.observability import tracing

        tracing._initialized = False
        with patch.dict("os.environ", {"OTEL_EXPORTER_OTLP_ENDPOINT": ""}, clear=False):
            tracing.init_tracing()
        assert tracing._initialized is False

    def test_get_tracer_returns_object(self):
        from src.observability.tracing import get_tracer

        tracer = get_tracer("test")
        assert hasattr(tracer, "start_as_current_span")

    def test_traced_decorator_sync(self):
        from src.observability.tracing import traced

        @traced("test-span")
        def add(a, b):
            return a + b

        assert add(1, 2) == 3

    def test_traced_decorator_propagates_exception(self):
        from src.observability.tracing import traced

        @traced("fail-span")
        def boom():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            boom()

    def test_span_context_manager(self):
        from src.observability.tracing import span

        with span("my-span") as s:
            s.set_attribute("key", "value")

    def test_span_context_manager_exception(self):
        from src.observability.tracing import span

        with pytest.raises(RuntimeError):
            with span("fail-span"):
                raise RuntimeError("test")

    def test_noop_tracer_methods(self):
        from src.observability.tracing import _NoOpTracer, _NoOpSpan

        tracer = _NoOpTracer()
        s = tracer.start_span("x")
        assert isinstance(s, _NoOpSpan)
        s.set_attribute("a", 1)
        s.set_status(None, "desc")
        s.record_exception(Exception("e"))
        s.add_event("ev")


# ---------------------------------------------------------------------------
# AI Metrics
# ---------------------------------------------------------------------------
class TestAIMetrics:
    def test_record_llm_request_ok(self):
        from src.observability.ai_metrics import LLM_REQUESTS, record_llm_request

        before = _sample_total(LLM_REQUESTS, {"provider": "test", "model": "m1", "status": "ok"})
        record_llm_request("test", "m1", tokens_in=100, tokens_out=50, latency_s=1.2, cost=0.01)
        after = _sample_total(LLM_REQUESTS, {"provider": "test", "model": "m1", "status": "ok"})
        assert after - before == 1.0

    def test_record_llm_request_error(self):
        from src.observability.ai_metrics import LLM_ERRORS, record_llm_request

        before = _sample_total(LLM_ERRORS, {"provider": "test", "model": "m1", "error_type": "timeout"})
        record_llm_request("test", "m1", tokens_in=0, tokens_out=0, latency_s=5.0, cost=0.0, error="timeout")
        after = _sample_total(LLM_ERRORS, {"provider": "test", "model": "m1", "error_type": "timeout"})
        assert after - before == 1.0

    def test_record_security_event_prompt_injection(self):
        from src.observability.ai_metrics import PROMPT_INJECTION_DETECTED, record_security_event

        before = _sample_total(PROMPT_INJECTION_DETECTED, {"risk_level": "high"})
        record_security_event("prompt_injection", details={"risk_level": "high"})
        after = _sample_total(PROMPT_INJECTION_DETECTED, {"risk_level": "high"})
        assert after - before == 1.0

    def test_record_security_event_ssrf(self):
        from src.observability.ai_metrics import SSRF_BLOCKED, record_security_event

        before = _sample_total(SSRF_BLOCKED, {})
        record_security_event("ssrf_blocked")
        after = _sample_total(SSRF_BLOCKED, {})
        assert after - before == 1.0

    def test_record_security_event_tool_blocked(self):
        from src.observability.ai_metrics import TOOL_BLOCKED, record_security_event

        before = _sample_total(TOOL_BLOCKED, {"tool": "shell", "reason": "policy"})
        record_security_event("tool_blocked", details={"tool": "shell", "reason": "policy"})
        after = _sample_total(TOOL_BLOCKED, {"tool": "shell", "reason": "policy"})
        assert after - before == 1.0

    def test_record_tool_execution_success(self):
        from src.observability.ai_metrics import TOOL_EXECUTIONS, record_tool_execution

        before = _sample_total(TOOL_EXECUTIONS, {"tool": "search", "status": "ok"})
        record_tool_execution("search", latency_s=0.5, success=True)
        after = _sample_total(TOOL_EXECUTIONS, {"tool": "search", "status": "ok"})
        assert after - before == 1.0

    def test_record_tool_execution_blocked(self):
        from src.observability.ai_metrics import TOOL_EXECUTIONS, record_tool_execution

        before = _sample_total(TOOL_EXECUTIONS, {"tool": "rm", "status": "blocked"})
        record_tool_execution("rm", latency_s=0.0, blocked_reason="dangerous")
        after = _sample_total(TOOL_EXECUTIONS, {"tool": "rm", "status": "blocked"})
        assert after - before == 1.0


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------
class TestAlerting:
    def test_generate_prometheus_rules_structure(self):
        from src.observability.alerting import generate_prometheus_rules

        rules = generate_prometheus_rules()
        assert "groups" in rules
        group = rules["groups"][0]
        assert group["name"] == "superagente-alerts"
        assert len(group["rules"]) == 7

    def test_all_rules_have_required_fields(self):
        from src.observability.alerting import generate_prometheus_rules

        rules = generate_prometheus_rules()
        for rule in rules["groups"][0]["rules"]:
            assert "alert" in rule
            assert "expr" in rule
            assert "for" in rule
            assert "labels" in rule
            assert "annotations" in rule
            assert "severity" in rule["labels"]

    def test_format_slack_alert(self):
        from src.observability.alerting import format_slack_alert

        payload = format_slack_alert({
            "status": "firing",
            "labels": {"alertname": "HighLLMErrorRate", "severity": "warning"},
            "annotations": {"summary": "Error rate high", "description": "Details here"},
        })
        assert "blocks" in payload
        assert len(payload["blocks"]) >= 2

    def test_format_discord_alert(self):
        from src.observability.alerting import format_discord_alert

        payload = format_discord_alert({
            "status": "firing",
            "labels": {"alertname": "CostSpike", "severity": "critical"},
            "annotations": {"summary": "Cost spike", "description": "Over budget"},
        })
        assert "embeds" in payload
        assert payload["embeds"][0]["title"].startswith("[FIRING]")

    def test_format_slack_multiple_alerts(self):
        from src.observability.alerting import format_slack_alert

        payload = format_slack_alert({
            "alerts": [
                {"status": "firing", "labels": {"alertname": "A", "severity": "critical"}, "annotations": {"summary": "s1", "description": "d1"}},
                {"status": "resolved", "labels": {"alertname": "B", "severity": "info"}, "annotations": {"summary": "s2", "description": "d2"}},
            ]
        })
        assert len(payload["blocks"]) == 3  # header + 2 alerts


# ---------------------------------------------------------------------------
# Dashboard JSON validity
# ---------------------------------------------------------------------------
class TestDashboards:
    @pytest.mark.parametrize("filename", [
        "grafana_llm.json",
        "grafana_security.json",
        "grafana_cost.json",
    ])
    def test_dashboard_is_valid_json(self, filename):
        path = DASHBOARD_DIR / filename
        assert path.exists(), f"{filename} not found"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "panels" in data
        assert "title" in data
        assert "uid" in data

    @pytest.mark.parametrize("filename", [
        "grafana_llm.json",
        "grafana_security.json",
        "grafana_cost.json",
    ])
    def test_dashboard_panels_have_targets(self, filename):
        data = json.loads((DASHBOARD_DIR / filename).read_text(encoding="utf-8"))
        for panel in data["panels"]:
            assert "targets" in panel, f"Panel '{panel.get('title')}' missing targets"
            for target in panel["targets"]:
                assert "expr" in target, f"Target in '{panel.get('title')}' missing expr"

    def test_llm_dashboard_has_variables(self):
        data = json.loads((DASHBOARD_DIR / "grafana_llm.json").read_text(encoding="utf-8"))
        variables = {v["name"] for v in data["templating"]["list"]}
        assert "provider" in variables
        assert "model" in variables

    def test_cost_dashboard_has_variables(self):
        data = json.loads((DASHBOARD_DIR / "grafana_cost.json").read_text(encoding="utf-8"))
        variables = {v["name"] for v in data["templating"]["list"]}
        assert "provider" in variables
        assert "model" in variables


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sample_total(metric, labels: dict) -> float:
    """Reads the current value of a prometheus metric with the given labels."""
    for m in metric.collect():
        for sample in m.samples:
            if not sample.name.endswith("_total") and not sample.name.endswith("_created"):
                if sample.name == m.name:
                    pass
            sample_labels = {k: v for k, v in sample.labels.items()}
            if all(sample_labels.get(k) == v for k, v in labels.items()):
                if sample.name.endswith("_total") or not labels:
                    return sample.value
    return 0.0
