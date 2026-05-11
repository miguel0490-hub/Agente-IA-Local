"""Alert rules for Prometheus/Alertmanager.

Generates Prometheus alerting rules and provides webhook helpers for Slack/Discord.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any


def generate_prometheus_rules() -> dict[str, Any]:
    """Generates a Prometheus alerting-rules dict (YAML-compatible structure)."""
    return {
        "groups": [
            {
                "name": "superagente-alerts",
                "rules": [
                    {
                        "alert": "HighLLMErrorRate",
                        "expr": "rate(superagente_llm_errors_total[5m]) > 0.1",
                        "for": "5m",
                        "labels": {"severity": "warning"},
                        "annotations": {
                            "summary": "LLM error rate is elevated",
                            "description": (
                                "LLM error rate has exceeded 0.1 req/s for 5 minutes. "
                                "Current value: {{ $value | printf \"%.2f\" }} req/s."
                            ),
                        },
                    },
                    {
                        "alert": "HighLLMLatency",
                        "expr": (
                            "histogram_quantile(0.95, "
                            "rate(superagente_llm_latency_seconds_bucket[5m])) > 30"
                        ),
                        "for": "5m",
                        "labels": {"severity": "warning"},
                        "annotations": {
                            "summary": "LLM p95 latency exceeds 30 s",
                            "description": (
                                "The 95th-percentile LLM response time is above 30 seconds. "
                                "Current p95: {{ $value | printf \"%.1f\" }}s."
                            ),
                        },
                    },
                    {
                        "alert": "CostSpike",
                        "expr": "rate(superagente_llm_cost_usd_total[1h]) > 10",
                        "for": "15m",
                        "labels": {"severity": "critical"},
                        "annotations": {
                            "summary": "LLM cost spike detected",
                            "description": (
                                "Hourly LLM spend rate exceeds $10/h. "
                                "Current rate: ${{ $value | printf \"%.2f\" }}/h."
                            ),
                        },
                    },
                    {
                        "alert": "PromptInjectionSurge",
                        "expr": "rate(superagente_prompt_injection_total[5m]) > 1",
                        "for": "2m",
                        "labels": {"severity": "critical"},
                        "annotations": {
                            "summary": "Prompt-injection surge detected",
                            "description": (
                                "More than 1 prompt-injection attempt/s detected over 5 min. "
                                "Investigate immediately."
                            ),
                        },
                    },
                    {
                        "alert": "CircuitBreakerOpen",
                        "expr": "superagente_circuit_breaker_state > 0",
                        "for": "1m",
                        "labels": {"severity": "warning"},
                        "annotations": {
                            "summary": "Circuit breaker is open for {{ $labels.service }}",
                            "description": (
                                "Service {{ $labels.service }} circuit breaker has been open "
                                "for more than 1 minute."
                            ),
                        },
                    },
                    {
                        "alert": "HighActiveUsers",
                        "expr": "superagente_active_users > 100",
                        "for": "5m",
                        "labels": {"severity": "info"},
                        "annotations": {
                            "summary": "High number of concurrent users",
                            "description": (
                                "Active users exceeded 100 for 5 minutes. "
                                "Consider scaling. Current: {{ $value }}."
                            ),
                        },
                    },
                    {
                        "alert": "PodDown",
                        "expr": "up{job=\"superagente\"} == 0",
                        "for": "2m",
                        "labels": {"severity": "critical"},
                        "annotations": {
                            "summary": "SuperAgente pod is down",
                            "description": (
                                "Instance {{ $labels.instance }} has been unreachable "
                                "for more than 2 minutes."
                            ),
                        },
                    },
                ],
            }
        ]
    }


def format_slack_alert(alert_data: dict[str, Any]) -> dict[str, Any]:
    """Formats a Prometheus/Alertmanager alert payload for a Slack webhook."""
    alerts = alert_data.get("alerts", [alert_data])
    blocks: list[dict[str, Any]] = []

    for alert in alerts:
        status = alert.get("status", "firing")
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        colour = "#e01e5a" if status == "firing" else "#2eb886"
        fingerprint = alert.get("fingerprint", _fingerprint(alert))

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*[{status.upper()}]* {labels.get('alertname', 'Alert')}\n"
                        f"Severity: `{labels.get('severity', 'unknown')}`\n"
                        f"{annotations.get('summary', '')}\n"
                        f"_{annotations.get('description', '')}_"
                    ),
                },
            }
        )

    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "SuperAgente Alert Notification",
                },
            },
            *blocks,
        ],
    }


def format_discord_alert(alert_data: dict[str, Any]) -> dict[str, Any]:
    """Formats a Prometheus/Alertmanager alert payload for a Discord webhook."""
    alerts = alert_data.get("alerts", [alert_data])
    embeds: list[dict[str, Any]] = []

    for alert in alerts:
        status = alert.get("status", "firing")
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        colour = 0xE01E5A if status == "firing" else 0x2EB886

        embeds.append(
            {
                "title": f"[{status.upper()}] {labels.get('alertname', 'Alert')}",
                "description": annotations.get("description", ""),
                "color": colour,
                "fields": [
                    {"name": "Severity", "value": labels.get("severity", "unknown"), "inline": True},
                    {"name": "Summary", "value": annotations.get("summary", ""), "inline": False},
                ],
            }
        )

    return {"content": "SuperAgente Alert", "embeds": embeds}


def _fingerprint(alert: dict[str, Any]) -> str:
    raw = json.dumps(alert.get("labels", {}), sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
