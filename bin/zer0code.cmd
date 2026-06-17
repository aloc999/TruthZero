@echo off
setlocal

set "PACKAGE_DIR=%~dp0.."
set "PYTHON=%PACKAGE_DIR%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo.
    echo   ZER0CODE: Python venv not found.
    echo   Run: npm rebuild zer0code
    echo.
    exit /b 1
)

"%PYTHON%" -m zer0code %*
