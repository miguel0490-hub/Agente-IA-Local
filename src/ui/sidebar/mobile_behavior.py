"""Mobile sidebar behavior helpers."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components


_SIDEBAR_COLLAPSE_JS = """
<script>
(function() {
    if (window.innerWidth > 768) return;
    var doc = window.parent.document;
    function tryCollapse(attempts) {
        if (attempts <= 0) return;
        var btn = doc.querySelector('button[data-testid="stSidebarCollapse"]')
              || doc.querySelector('[data-testid="stSidebarCollapseButton"] button');
        var sidebar = doc.querySelector('section[data-testid="stSidebar"]');
        if (btn && sidebar && sidebar.getAttribute('aria-expanded') === 'true') {
            btn.click();
        } else if (!btn) {
            setTimeout(function() { tryCollapse(attempts - 1); }, 200);
        }
    }
    tryCollapse(10);
})();
</script>
"""


def apply_mobile_sidebar_autoclose() -> None:
    """Auto-collapses sidebar on mobile after actions that request it."""
    if not st.session_state.get("auto_close_sidebar"):
        return

    st.session_state.auto_close_sidebar = False
    components.html(_SIDEBAR_COLLAPSE_JS, height=0, width=0)


def apply_mobile_sidebar_default_closed() -> None:
    """Collapses sidebar on mobile on first load of the session."""
    if st.session_state.get("_mobile_sidebar_collapsed"):
        return
    st.session_state._mobile_sidebar_collapsed = True
    components.html(_SIDEBAR_COLLAPSE_JS, height=0, width=0)
