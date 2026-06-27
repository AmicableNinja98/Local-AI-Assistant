@echo off
title Asistente IA Local

:: -----------------------------------------------
:: CONFIGURACIÓN — cambia estas rutas si es necesario
:: -----------------------------------------------
set RUTA_PYTHON=C:\dev\python\asistente_ia\venv\Scripts\python.exe
set RUTA_ASISTENTE=C:\dev\python\asistente_ia\frontend\cli.py

"%RUTA_PYTHON%" "%RUTA_ASISTENTE%"