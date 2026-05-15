@echo off
title SuperAgente IA Pro
cd /d "%~dp0\.."
cls
set "PY=%CD%\venv\Scripts\python.exe"
if not exist "%PY%" (
    echo.
    echo No se encontro "%PY%".
    echo Crea el entorno en la raiz del proyecto: python -m venv venv
    echo Luego instala dependencias: venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
REM Puerto: si defines STREAMLIT_PORT antes de ejecutar este .bat, se respeta; si no, se elige 8501-8519 libre.
if not defined STREAMLIT_PORT (
    for /f "usebackq delims=" %%p in (`"%PY%" "%~dp0pick_streamlit_port.py"`) do set "STREAMLIT_PORT=%%p"
)
if not defined STREAMLIT_PORT set "STREAMLIT_PORT=8501"
echo =======================================================
echo   Despertando al SuperAgente IA Pro...
echo   Puerto: %STREAMLIT_PORT%  (http://localhost:%STREAMLIT_PORT%)
echo   Se abrira una pestana en tu navegador.
echo =======================================================
REM Usar python -m streamlit evita depender de PATH tras "activate".
REM Si el proyecto se movio desde otra carpeta, activate.bat puede seguir apuntando al venv antiguo.
"%PY%" -m streamlit run "%CD%\app.py" --server.port %STREAMLIT_PORT%
pause