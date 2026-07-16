@echo off
title Aprobar Ticket de Correo Externo
color 0B
echo ===================================================
echo   Aprobacion y Reseteo Manual (Tickets Externos)
echo ===================================================
echo.
set /p ticket="Ingresa el numero de Ticket (ej. UTM-85305): "
set /p matricula="Ingresa la matricula del alumno (ej. 2320246): "
echo.
cd "C:\Users\DomingoGH245\Desktop\ia\UTM_Soporte_IA"
C:\Users\DomingoGH245\anaconda3\python.exe -u aprobar_ticket.py %ticket% %matricula%
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause > nul
