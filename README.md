# AI-Powered Job Matching System

This application is a job matching system that uses Google's Gemini 1.5 AI to analyze job applications. The system helps recruiters find the best candidates by automatically analyzing resumes against job requirements, and provides applicants with constructive feedback.

## Features

### For Recruiters
- Post job listings with detailed requirements and skill weights
- Review applications with AI-generated match scores
- Get insights into candidate skills and qualifications
- Send automated, personalized feedback to applicants

### For Applicants
- Apply to jobs by uploading resume
- Receive a match score showing fit for the position
- Get constructive feedback on skills to improve
- View detailed analysis of strengths and improvement areas

## Technical Setup

### Prerequisites
- Python 3.8 or higher
- MongoDB (running locally or accessible)
- Google Gemini API key

### Installation

1. Clone the repository
```
git clone <repository-url>
cd <repository-directory>
```

2. Create and activate a virtual environment
```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```
pip install -r requirements.txt
```

4. Set up environment variables
```
cp .env.example .env
```
Edit the `.env` file and add your Google Gemini API key

### Running the Application

1. Start the main API server
```
python auth.py
```

2. Start the AI analysis server
```
python job_matching_ai.py
```

The main API server runs on port 5001, and the AI analysis server runs on port 5002.

## API Endpoints

### Main API (auth.py)
- `/api/jobs/<job_id>/apply` - Submit a job application
- `/api/applications/status` - Check application status and feedback
- `/api/applications/<application_id>/status` - Update application status

### AI API (job_matching_ai.py)
- `/api/analyze-application` - Analyze a job application
- `/api/update-application-status` - Generate feedback when status changes
- `/api/get-application-feedback` - Get detailed feedback for applicants

## How It Works

1. When an applicant applies for a job, their resume is automatically analyzed against the job requirements
2. The AI extracts text from the resume and compares it with job skills and requirements
3. A match score is calculated based on weighted skill importance
4. When recruiters review applications, they see match scores and can make decisions
5. When an application is accepted or rejected, the AI generates personalized feedback
6. Applicants can view detailed feedback and suggestions for improvement

## Dependencies
- Flask - Web framework
- PyMongo - MongoDB connection
- Flask-JWT-Extended - Authentication
- Google Generative AI - AI analysis
- PyMuPDF - PDF text extraction
- python-docx - DOCX text extraction

## Getting a Gemini API Key

1. Visit https://ai.google.dev/
2. Sign up for API access
3. Create an API key
4. Add the key to your `.env` file 