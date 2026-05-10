@echo off
title SuperAgente IA Pro
cls
echo =======================================================
echo   Despertando al SuperAgente IA Pro...
echo   Se abrira una pestana en tu navegador.
echo ==========================================
call venv\Scripts\activate
streamlit run app.py
pause