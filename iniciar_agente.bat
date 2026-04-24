@echo off
title Agente IA Local v2.0
color 0A
echo ==========================================
echo   Despertando al Agente de IA Local v2.0...
echo   Se abrira una pestana en tu navegador.
echo ==========================================
call venv\Scripts\activate
streamlit run src\agente.py
pause