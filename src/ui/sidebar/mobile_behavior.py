"""Mobile sidebar behavior helpers."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components


def apply_mobile_sidebar_autoclose() -> None:
    """Auto-collapses sidebar on mobile after actions that request it."""
    if not st.session_state.get("auto_close_sidebar"):
        return

    st.session_state.auto_close_sidebar = False
    components.html(
        """
        <script>
        if (window.innerWidth <= 768) {
            const collapseBtn = window.parent.document.querySelector('button[data-testid="stSidebarCollapse"]');
            if (collapseBtn) {
                const sidebar = window.parent.document.querySelector('section[data-testid="stSidebar"]');
                if (sidebar && sidebar.getAttribute('aria-expanded') === 'true') {
                    collapseBtn.click();
                }
            }
        }
        </script>
        """,
        height=0,
        width=0,
    )
