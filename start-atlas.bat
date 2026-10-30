@echo off
setlocal
where python >nul 2>nul || (echo Python is required.& exit /b 1)
where npm >nul 2>nul || (echo npm is required.& exit /b 1)
cd backend
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
start "ATLAS Backend" cmd /k "uvicorn app.main:app --reload --port 8000"
cd ..\frontend
call npm install
echo ATLAS frontend: http://localhost:5173
echo API docs: http://localhost:8000/docs
call npm run dev
