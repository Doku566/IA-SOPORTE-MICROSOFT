@echo off
title UTM Soporte-IA: Orquestador de Correos
color 0A

echo ===================================================
echo   Iniciando Sistema de Soporte Automatizado (IA)
echo ===================================================
echo.

cd "C:\Users\DomingoGH245\Desktop\ia\UTM_Soporte_IA"

echo [1/3] Iniciando el cerebro de la IA (Ollama)...
:: Iniciar Ollama de forma silenciosa
start "" /MIN "C:\Users\DomingoGH245\AppData\Local\Programs\Ollama\ollama.exe" serve

:: Esperar 5 segundos para que cargue la IA (ping es mas seguro que timeout)
ping 127.0.0.1 -n 6 > nul

echo [2/3] Iniciando Servidor Web de Reseteo de Contrasenas...
:: Iniciar FastAPI en una ventana minimizada separada
start "UTM Web API" /MIN cmd /c "C:\Users\DomingoGH245\anaconda3\python.exe -m uvicorn main:app --port 8000"

echo [3/3] Iniciando Orquestador (Lector de Correos)...
echo.
echo El sistema esta en linea. Presiona Ctrl+C si deseas detenerlo.
echo ---------------------------------------------------
:: Correr el orquestador en esta ventana principal
C:\Users\DomingoGH245\anaconda3\python.exe -u orchestrator.py

pause
