import subprocess
import os
import time
import threading
import sys
import signal
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def run_flask():
    flask_process = subprocess.Popen(
        ['python', 'ats.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print("🚀 Flask backend started on http://localhost:5000")
    
    for line in flask_process.stdout:
        print(f"[Flask] {line.strip()}")
    
    return flask_process

def run_auth_server():
    auth_process = subprocess.Popen(
        ['python', 'auth.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print("🔐 Auth server started on http://localhost:5001")
    
    for line in auth_process.stdout:
        print(f"[Auth] {line.strip()}")
    
    return auth_process

def run_job_matching_ai():
    # Check if Google API key is set
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("⚠️ GOOGLE_API_KEY not found in environment variables.")
        print("⚠️ Job matching AI service requires a Google Gemini API key.")
        print("⚠️ Add your API key to the .env file: GOOGLE_API_KEY=your-api-key-here")
        return None
    
    ai_process = subprocess.Popen(
        ['python', 'job_matching_ai.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print("🧠 Job Matching AI service started on http://localhost:5002")
    
    for line in ai_process.stdout:
        print(f"[AI] {line.strip()}")
    
    return ai_process

def run_nextjs():
    nextjs_process = subprocess.Popen(
        ['npm', 'run', 'dev'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print("🚀 Next.js frontend started on http://localhost:3000")
    
    for line in nextjs_process.stdout:
        print(f"[Next.js] {line.strip()}")
    
    return nextjs_process

def init_database():
    print("Initializing MongoDB database with sample users...")
    try:
        subprocess.check_call([sys.executable, "init_db.py"])
    except subprocess.CalledProcessError as e:
        print(f"Warning: Database initialization failed: {e}")
        print("You may need to install MongoDB or ensure it's running.")

def main():
    print("""
    ╭───────────────────────────────────────────────╮
    │         AI-Powered Job Matching System        │
    │      with Resume Analysis & Feedback          │
    ╰───────────────────────────────────────────────╯
    """)
    
    print("Starting AI Resume Analyzer & Job Matching application...")
    
    # Check if required packages are installed
    try:
        install_requirements()
    except Exception as e:
        print(f"Error installing requirements: {e}")
        return
    
    # Initialize the database
    init_database()
    
    # Start Flask backend
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start Auth server
    auth_thread = threading.Thread(target=run_auth_server)
    auth_thread.daemon = True
    auth_thread.start()
    
    # Start Job Matching AI service
    ai_thread = threading.Thread(target=run_job_matching_ai)
    ai_thread.daemon = True
    ai_thread.start()
    
    # Wait for servers to start
    time.sleep(2)
    
    # Start Next.js frontend
    nextjs_thread = threading.Thread(target=run_nextjs)
    nextjs_thread.daemon = True
    nextjs_thread.start()
    
    print("\n🔥 AI Job Matching System is running!")
    print("📊 Backend API: http://localhost:5000")
    print("🔐 Auth API: http://localhost:5001")
    print("🧠 Job Matching AI: http://localhost:5002")
    print("🌐 Frontend UI: http://localhost:3000")
    print("\nFeatures:")
    print("  • Upload your resume for ATS compatibility analysis")
    print("  • Compare with job descriptions for targeted feedback")
    print("  • Get personalized skill development recommendations")
    print("  • AI-powered job matching with match scores")
    print("  • Automated feedback for accepted/rejected applications")
    print("\nPress Ctrl+C to stop the application\n")
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down application...")
        sys.exit(0)

def install_requirements():
    # Install Python packages
    print("Installing Python requirements...")
    python_packages = [
        "flask", 
        "flask-cors", 
        "python-dotenv", 
        "google-generativeai", 
        "PyPDF2",
        "flask-pymongo",
        "pymongo",
        "bcrypt",
        "flask-jwt-extended",
        "PyMuPDF",
        "python-docx",
        "bson"
    ]
    
    for package in python_packages:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        except subprocess.CalledProcessError:
            print(f"Failed to install {package}")
            raise

if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    main() 