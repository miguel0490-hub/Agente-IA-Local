@echo off
title SuperAgente IA Pro v4.1
color 0A
echo ==========================================
echo   Despertando al SuperAgente IA Pro v4.1...
echo   Se abrira una pestana en tu navegador.
echo ==========================================
call venv\Scripts\activate
streamlit run app.py
pause