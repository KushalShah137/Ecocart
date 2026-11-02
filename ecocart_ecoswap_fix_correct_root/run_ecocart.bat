@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo ERROR: .venv not found. Create it with: py -m venv .venv
  echo Then run: .venv\Scripts\activate ^& pip install -r requirements.txt
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
echo.
echo [1/3] Checking Oracle connection...
python -c "from ecocart.db import get_connection; c=get_connection(); print('Oracle connection OK:', c.username); c.close()"
if errorlevel 1 goto failed
echo.
echo [2/3] Applying schema, migration, PL/SQL, and demo seed data...
python scripts\init_db.py
if errorlevel 1 goto failed
echo.
echo [3/3] Starting EcoCart at http://127.0.0.1:5000 ...
python app.py
goto end
:failed
echo.
echo EcoCart setup did not complete. Read the first ERROR above and fix it before retrying.
pause
:end
endlocal
