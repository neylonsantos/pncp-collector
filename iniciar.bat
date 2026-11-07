@echo off
title PNCP Collector and Analyzer
echo ==================================================================
echo   PNCP Collector and Analyzer
echo   Sistema de Captura de Editais Governamentais
echo ==================================================================
echo.

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Python encontrado. Iniciando aplicacao...
    python app.py
    goto :eof
)

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Python Launcher encontrado. Iniciando aplicacao...
    py app.py
    goto :eof
)

echo.
echo [ERRO] Python nao foi encontrado no seu computador!
echo Instale o Python 3 em: https://www.python.org/downloads/
echo IMPORTANTE: Marque a caixa "Add Python to PATH" durante a instalacao.
echo.
pause
