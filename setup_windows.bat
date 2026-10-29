@echo off
setlocal
cd /d "%~dp0"
py -3.12 --version >nul 2>&1
if errorlevel 1 (
  echo Install Python 3.12 for Windows from python.org with the Python launcher enabled.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
if not exist ".env" copy /y ".env.example" ".env" >nul
.venv\Scripts\python.exe -m unittest discover -s tests -v
if errorlevel 1 goto fail
echo.
echo Setup complete. Add your keys and Gemini model ID to .env, then run launch_windows.bat.
echo Keep .env private. Do not paste API keys into chat or source code.
pause
exit /b 0
:fail
echo Setup failed. Read the error above. Check internet access and Python installation.
pause
exit /b 1
