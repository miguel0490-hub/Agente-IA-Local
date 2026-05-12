"""In-app notification center for user alerts and admin messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import streamlit as st

from src.core.i18n import t


@dataclass
class Notification:
    """A single notification."""
    id: str
    title: str
    message: str
    type: str = "info"
    read: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))


def _get_notifications() -> list[Notification]:
    """Returns the notification list from session state."""
    if "notifications" not in st.session_state:
        st.session_state.notifications = []
    return st.session_state.notifications


def add_notification(title: str, message: str, type: str = "info") -> None:
    """Adds a notification to the session."""
    import uuid
    notifs = _get_notifications()
    notifs.insert(0, Notification(
        id=uuid.uuid4().hex[:8],
        title=title,
        message=message,
        type=type,
    ))
    if len(notifs) > 50:
        notifs.pop()


def get_unread_count() -> int:
    """Returns count of unread notifications."""
    return sum(1 for n in _get_notifications() if not n.read)


def render_notification_center() -> None:
    """Renders the notification list (intended to be called inside a dialog or container)."""
    notifs = _get_notifications()
    unread = get_unread_count()

    if not notifs:
        st.info(t("notifications_none"))
        return

    if unread > 0 and st.button(t("notifications_mark_all"), key="mark_all_read", use_container_width=True):
        for n in notifs:
            n.read = True
        st.rerun()

    for n in notifs[:20]:
        icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(n.type, "ℹ️")
        style = "opacity: 0.6;" if n.read else "font-weight: bold;"
        st.markdown(
            f"<div style='{style} padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.08);'>"
            f"{icon} <strong>{n.title}</strong><br>"
            f"<span style='font-size: 13px; color: #94A3B8;'>{n.message}</span><br>"
            f"<span style='font-size: 11px; color: #64748B;'>{n.created_at}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if not n.read:
            n.read = True
