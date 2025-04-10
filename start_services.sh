#!/bin/bash

echo "Starting Job Matching System services..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create a .env file based on .env.example with your Google API key"
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*)
        # Windows
        source venv/Scripts/activate
        ;;
    *)
        # Unix-like
        source venv/bin/activate
        ;;
esac

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Start main API server in background
echo "Starting main API server on port 5001..."
python auth.py > auth_log.txt 2>&1 &
AUTH_PID=$!

# Give the main server time to start
sleep 2

# Start AI server in background
echo "Starting AI Analysis server on port 5002..."
python job_matching_ai.py > ai_log.txt 2>&1 &
AI_PID=$!

# Display startup message
echo ""
echo "Job Matching System started!"
echo "Main API: http://localhost:5001"
echo "AI API: http://localhost:5002"
echo ""
echo "Press Ctrl+C to stop all services"

# Handle cleanup on exit
trap "echo 'Stopping services...'; kill $AUTH_PID $AI_PID; exit" INT TERM EXIT

# Wait for user to press Ctrl+C
wait 