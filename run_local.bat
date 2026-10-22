@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto ready
where py >nul 2>&1
if not errorlevel 1 (
 py -3 -m venv .venv
) else (
 python -m venv .venv
)
if errorlevel 1 goto failed
:ready
set "PYTHON=.venv\Scripts\python.exe"
"%PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto failed
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto failed
"%PYTHON%" scripts\bootstrap.py
if errorlevel 1 goto failed
"%PYTHON%" scripts\validate_environment.py
if errorlevel 1 goto failed
"%PYTHON%" -m pytest -q
if errorlevel 1 goto failed
"%PYTHON%" -m streamlit run app.py --server.port=8505 --server.address=127.0.0.1
exit /b %errorlevel%
:failed
echo Startup stopped. Review the error above. Python 3.11+ and dependency installation are required.
exit /b 1
