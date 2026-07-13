@echo off
setlocal

cd /d "%~dp0"

python --version >nul 2>nul
if %errorlevel%==0 (
    python server.py
    goto :end
)

py --version >nul 2>nul
if %errorlevel%==0 (
    py server.py
    goto :end
)

echo.
echo [ERROR] Python was not found.
echo Please install Python 3 and enable "Add python.exe to PATH" during installation.
echo Download: https://www.python.org/downloads/windows/
echo.
echo After installation, check one of these commands:
echo   python --version
echo   py --version
echo.
pause

:end
endlocal
