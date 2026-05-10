"""
Script manual (no pytest) para comprobar que pdfkit/wkhtmltopdf están disponibles en el entorno.

Ejecutar con Streamlit: ``streamlit run scripts/manual_pdfkit_probe.py``
"""

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.file_factory import HAS_PDFKIT, PDFKIT_CONFIG

st.write(f"Python path: {sys.executable}")
st.write(f"HAS_PDFKIT: {HAS_PDFKIT}")
st.write(f"PDFKIT_CONFIG: {getattr(PDFKIT_CONFIG, 'wkhtmltopdf', 'N/A')}")
