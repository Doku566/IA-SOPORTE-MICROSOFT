@echo off
title Enviando Correo Manual
color 0A
echo ===================================================
echo   Enviando correo con contrasenas a Uziel...
echo ===================================================
cd "C:\Users\DomingoGH245\Desktop\ia\UTM_Soporte_IA"
C:\Users\DomingoGH245\anaconda3\python.exe -u send_manual.py
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause > nul
