@echo off
REM Contoso REST API Scraper launcher. Creates the venv on first run if it is missing.
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo First run: creating the Python environment, please wait...
    python -m venv venv || (echo Python 3.11+ is required. & pause & exit /b 1)
    venv\Scripts\python.exe -m pip install --upgrade pip
    venv\Scripts\python.exe -m pip install -r requirements.txt || (echo Package install failed. & pause & exit /b 1)
)
start "" "venv\Scripts\pythonw.exe" -m restscraper
