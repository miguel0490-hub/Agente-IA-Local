"""PWA support: injects manifest and meta tags for mobile installability."""

from __future__ import annotations

import streamlit as st


def inject_pwa_meta() -> None:
    """Injects PWA manifest link and mobile meta tags into the page."""
    pwa_html = """
    <link rel="manifest" href="/app/static/manifest.json">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SuperAgente IA Pro">
    <meta name="theme-color" content="#00F2FE">
    <link rel="apple-touch-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
    """
    st.markdown(pwa_html, unsafe_allow_html=True)
