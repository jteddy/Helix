@echo off
cd /d "%~dp0"
echo ================================
echo  Cearum Web - Setup
echo ================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [info] Python not found. Installing via winget...
    winget install -e --id Python.Python.3 --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo [error] winget install failed.
        echo         Install manually from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo [ok] Python installed. Restarting setup...
    pause
    call "%~f0"
    exit /b
)

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo ================================
echo  Done. Run start.bat to launch.
echo ================================
pause
