@echo off
title SuperAgente IA Pro
cd /d "%~dp0\.."
cls
echo =======================================================
echo   Despertando al SuperAgente IA Pro...
echo   Se abrira una pestana en tu navegador.
echo ==========================================
call venv\Scripts\activate
streamlit run app.py
pause