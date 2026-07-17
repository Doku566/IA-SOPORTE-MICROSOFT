@echo off
title Orquestador de Soporte IA - Microsoft 365
color 0A

echo ===================================================
echo   Iniciando Sistema de Soporte Automatizado (IA)
echo ===================================================
echo.

:: Cambiar al directorio del script
cd /d "%~dp0"

:: Cerrar instancias previas del orquestador para evitar respuestas duplicadas
powershell -Command "Get-WmiObject Win32_Process | Where-Object {$_.CommandLine -like '*orchestrator.py*'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" > nul 2>&1

echo [1/3] Iniciando el servicio de inferencia local (Ollama)...
:: Iniciar Ollama en modo local en segundo plano
start "" /MIN ollama serve

:: Esperar 5 segundos para asegurar la inicialización del motor de IA
ping 127.0.0.1 -n 6 > nul

echo [2/3] Verificando entorno virtual e iniciando Servidor Web de Gestión...
:: Iniciar FastAPI para gestión de tickets y verificación documental en puerto 8000
if exist "venv\Scripts\python.exe" (
    start "UTM Web API" /MIN cmd /c "venv\Scripts\python.exe -m uvicorn main:app --port 8000"
) else if exist "%USERPROFILE%\anaconda3\python.exe" (
    start "UTM Web API" /MIN cmd /c "%USERPROFILE%\anaconda3\python.exe -m uvicorn main:app --port 8000"
) else (
    start "UTM Web API" /MIN cmd /c "python -m uvicorn main:app --port 8000"
)

echo [3/3] Iniciando Orquestador (Conexión Microsoft Graph API)...
echo.
echo El sistema se encuentra en linea y monitoreando el buzon institucional.
echo Presiona Ctrl+C en esta consola si deseas finalizar los servicios.
echo ---------------------------------------------------

:: Correr el orquestador en la consola principal con el intérprete moderno
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -u orchestrator.py
) else if exist "%USERPROFILE%\anaconda3\python.exe" (
    "%USERPROFILE%\anaconda3\python.exe" -u orchestrator.py
) else (
    python -u orchestrator.py
)

pause
