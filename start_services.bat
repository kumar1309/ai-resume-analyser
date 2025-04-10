@echo off
echo Starting Job Matching System services...

REM Check if .env file exists
if not exist .env (
    echo Error: .env file not found!
    echo Please create a .env file based on .env.example with your Google API key
    exit /b 1
)

REM Check if virtual environment exists, create if not
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Start main API server in a new window
echo Starting main API server on port 5001...
start "Main API Server" cmd /c "python auth.py > auth_log.txt 2>&1"

REM Give the main server time to start
timeout /t 2 /nobreak > nul

REM Start AI server in a new window
echo Starting AI Analysis server on port 5002...
start "AI Analysis Server" cmd /c "python job_matching_ai.py > ai_log.txt 2>&1"

REM Display startup message
echo.
echo Job Matching System started!
echo Main API: http://localhost:5001
echo AI API: http://localhost:5002
echo.
echo Close the command windows to stop the services

REM Keep the console open
echo Press any key to exit this window (servers will continue running)...
pause > nul 