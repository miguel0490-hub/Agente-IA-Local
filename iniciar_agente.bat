@echo off
title Agente IA Local
color 0A
echo ==========================================
echo   Despertando al Agente de IA Local...
echo ==========================================
call venv\Scripts\activate
python src\agente.py
pause