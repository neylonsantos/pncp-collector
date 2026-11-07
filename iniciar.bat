@echo off
chcp 65001 >nul
title PNCP Collector & Analyzer
echo ==================================================================
echo   🚀 PNCP Collector & Analyzer
echo   Sistema de Captura e Mineração de Editais Governamentais
echo ==================================================================
echo.

:: Verifica se o comando python está no PATH
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Python localizado. Abrindo navegador...
    start http://localhost:8000
    python app.py
    goto end
)

:: Verifica se o iniciador py está disponível
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Python Launcher localizado. Abrindo navegador...
    start http://localhost:8000
    py app.py
    goto end
)

echo [ERRO] O Python não foi encontrado no seu sistema!
echo Por favor, instale o Python 3 através de: https://www.python.org/downloads/
echo (IMPORTANTE: Marque a opção "Add Python to PATH" durante a instalação)
echo.
pause

:end
