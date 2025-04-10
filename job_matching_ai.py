from flask import Flask, request, jsonify
import google.generativeai as genai
import os
import re
import json
from pymongo import MongoClient
import datetime
import base64
import fitz  # PyMuPDF for PDF handling
import docx  # python-docx for DOCX handling
import io
from dotenv import load_dotenv
from bson.objectid import ObjectId

# Load environment variables from .env file
load_dotenv()

# Configure Google Gemini API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set")

genai.configure(api_key=GOOGLE_API_KEY)

# Initialize Flask app
app = Flask(__name__)

# Set up MongoDB connection
MONGO_URI = "mongodb://localhost:27017/jobmatchdb"
client = MongoClient(MONGO_URI)
db = client.jobmatchdb

# Configure Gemini model
model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config={
        "temperature": 0.2,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
    }
)

def extract_text_from_pdf(pdf_data):
    """Extract text from PDF binary data."""
    try:
        # Convert base64 to binary if needed
        if isinstance(pdf_data, str) and pdf_data.startswith('data:application/pdf;base64,'):
            pdf_data = base64.b64decode(pdf_data.split(',')[1])
        
        # Open PDF from memory
        pdf_file = fitz.open(stream=pdf_data, filetype="pdf")
        text = ""
        
        # Extract text from each page
        for page_num in range(len(pdf_file)):
            page = pdf_file[page_num]
            text += page.get_text()
        
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return ""

def extract_text_from_docx(docx_data):
    """Extract text from DOCX binary data."""
    try:
        # Convert base64 to binary if needed
        if isinstance(docx_data, str) and docx_data.startswith('data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,'):
            docx_data = base64.b64decode(docx_data.split(',')[1])
        elif isinstance(docx_data, str) and docx_data.startswith('data:application/msword;base64,'):
            docx_data = base64.b64decode(docx_data.split(',')[1])
        
        # Open DOCX from memory
        doc = docx.Document(io.BytesIO(docx_data))
        
        # Extract text from paragraphs
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        print(f"Error extracting text from DOCX: {str(e)}")
        return ""

def extract_text_from_resume(resume_data):
    """Extract text from resume based on file type."""
    try:
        # Check if it's a base64 encoded file
        if isinstance(resume_data, str):
            if 'data:application/pdf;base64,' in resume_data:
                return extract_text_from_pdf(resume_data)
            elif 'data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,' in resume_data:
                return extract_text_from_docx(resume_data)
            elif 'data:application/msword;base64,' in resume_data:
                return extract_text_from_docx(resume_data)
            elif 'data:text/plain;base64,' in resume_data:
                # Plain text
                text_data = base64.b64decode(resume_data.split(',')[1]).decode('utf-8')
                return text_data
            elif resume_data.startswith('data:'):
                # Try to extract from the base64 data directly
                try:
                    # Get the MIME type
                    mime_type = resume_data.split(';')[0].split(':')[1]
                    # Get the base64 part
                    base64_data = resume_data.split(',')[1]
                    # Decode
                    decoded_data = base64.b64decode(base64_data)
                    
                    if 'pdf' in mime_type:
                        return extract_text_from_pdf(decoded_data)
                    elif 'word' in mime_type or 'docx' in mime_type or 'doc' in mime_type:
                        return extract_text_from_docx(decoded_data)
                    else:
                        return decoded_data.decode('utf-8', errors='ignore')
                except Exception as e:
                    print(f"Failed to decode unknown MIME type: {str(e)}")
                    return resume_data[:10000]  # Return a truncated version
        
        # If we couldn't determine the file type or extract text, return a portion of the data
        return resume_data[:10000] if isinstance(resume_data, str) else "Unable to extract text from resume"
    
    except Exception as e:
        print(f"Error in extract_text_from_resume: {str(e)}")
        return "Error extracting text from resume"

def analyze_job_application(resume_text, job_description, required_skills):
    """
    Analyze a job application using Gemini 1.5 to determine match score and provide feedback.
    Falls back to rule-based matching if Gemini API is unavailable.
    """
    try:
        # Format required skills for prompt
        skills_text = "\n".join([f"- {skill['name']} (Importance: {skill['weight']}%)" for skill in required_skills])
        
        # Create a detailed prompt for Gemini with improved scoring guidelines
        prompt = f"""
        You are an expert AI recruitment assistant. Your task is to analyze a candidate's resume against a job description and required skills.
        
        # Job Description:
        {job_description}
        
        # Required Skills (with importance weights):
        {skills_text}
        
        # Candidate's Resume:
        {resume_text}
        
        Perform a detailed analysis and provide the following outputs in a JSON structure:
        
        1. Calculate an overall match score (0-100) considering the weighted importance of each skill.
        Follow these improved scoring guidelines:
           - Be generous in recognizing skills - if the candidate mentions related technologies or frameworks, count them as partial matches
           - Prioritize relevant experience over keyword matching
           - Consider transferable skills and knowledge when direct mentions are missing
           - Start with a baseline score of 70 for candidates who have most of the core skills
           - Only reduce scores significantly when critical skills are completely missing
        
        2. For each required skill, determine if the candidate has it and assign a match score (0-100).
           - Consider related technologies as partial matches (e.g., if MERN is required, having MongoDB + React experience counts significantly)
           - Look for evidence of practical implementation, not just mentions of keywords
           - Consider both direct mentions and implied knowledge through projects or experience
        
        3. Identify skills the candidate is lacking or needs improvement on.
        
        4. Provide specific, constructive feedback on how the candidate could improve their qualifications for this role.
        
        5. Summarize the candidate's strengths relevant to this role.
        
        Return your analysis as JSON with the following structure:
        {{
            "overall_match_score": <0-100>,
            "skill_matches": [
                {{
                    "skill_name": "<name>",
                    "importance_weight": <0-100>,
                    "match_score": <0-100>,
                    "evidence": "<evidence from resume>"
                }},
                ...
            ],
            "missing_skills": [
                {{
                    "skill_name": "<name>",
                    "importance_weight": <0-100>,
                    "improvement_suggestion": "<specific suggestion>"
                }},
                ...
            ],
            "strengths": ["<strength1>", "<strength2>", ...],
            "improvement_areas": ["<area1>", "<area2>", ...],
            "detailed_feedback": "<constructive feedback paragraph>"
        }}
        
        IMPORTANT: 
        - Be generous and optimistic in your evaluation
        - Recognize both explicit mentions and implicit demonstrations of skills
        - Consider the overall profile and relevant experience, not just keyword matching
        - Start with a higher baseline score (70+) and only subtract if skills are clearly missing
        - For tech roles, recognize that familiarity with one technology often indicates ability to quickly learn related ones
        """
        
        try:
            # Try to generate response from Gemini with timeout
            response = model.generate_content(prompt)
            response_text = response.text
            
            # Extract JSON from the response
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                result_json = json.loads(json_match.group(1))
            else:
                try:
                    # Try direct parsing if no code blocks found
                    result_json = json.loads(response_text)
                except:
                    # If still can't parse, try to extract anything between curly braces
                    json_match = re.search(r'({.*})', response_text, re.DOTALL)
                    if json_match:
                        result_json = json.loads(json_match.group(1))
                    else:
                        raise ValueError("Could not extract JSON from Gemini response")
            
            # Apply additional score adjustments to ensure more balanced scoring
            if "overall_match_score" in result_json:
                # Adjust the final score to be more generous
                original_score = result_json["overall_match_score"]
                
                # Boost scores below 75 to be more optimistic
                if original_score < 75:
                    # Scale up low scores more aggressively
                    # Formula: new_score = original_score + (75 - original_score) * 0.4
                    # This gives a boost proportional to how far below 75 the score is
                    adjustment = (75 - original_score) * 0.4
                    result_json["overall_match_score"] = min(98, int(original_score + adjustment))
                    
                    # Add a note about the adjustment
                    result_json["score_note"] = "Score was adjusted to better reflect candidate potential and transferable skills."
            
            return result_json
        except Exception as e:
            print(f"Gemini API error: {str(e)}")
            print("Falling back to rule-based matching algorithm")
            # Fall back to rule-based matching
            return fallback_analyze_job_application(resume_text, job_description, required_skills)
    
    except Exception as e:
        print(f"Error in analyze_job_application: {str(e)}")
        import traceback
        traceback.print_exc()
        return fallback_analyze_job_application(resume_text, job_description, required_skills)

def fallback_analyze_job_application(resume_text, job_description, required_skills):
    """
    Fallback mechanism for resume analysis when Gemini API is unavailable.
    Uses rule-based matching to generate scores and feedback.
    """
    print("Using fallback analysis mechanism")
    try:
        # Calculate skill matches using keyword-based approach
        skill_matches = []
        missing_skills = []
        total_score = 0
        total_weight = 0
        resume_lower = resume_text.lower()
        
        # Analyze each required skill
        for skill in required_skills:
            skill_name = skill['name']
            importance_weight = skill['weight']
            total_weight += importance_weight
            
            # Determine if skill is in resume (simple keyword matching)
            skill_keywords = [skill_name.lower()]
            # Add related terms for common skills
            if skill_name.lower() == "javascript":
                skill_keywords.extend(["js", "typescript", "react", "vue", "angular", "node"])
            elif skill_name.lower() == "python":
                skill_keywords.extend(["django", "flask", "pandas", "numpy", "scikit", "jupyter"])
            elif skill_name.lower() == "java":
                skill_keywords.extend(["spring", "hibernate", "j2ee", "maven", "gradle"])
            
            # Calculate match score based on keyword presence
            skill_score = 0
            evidence = ""
            
            for keyword in skill_keywords:
                if keyword in resume_lower:
                    # Find the context around the keyword
                    keyword_index = resume_lower.find(keyword)
                    start_idx = max(0, keyword_index - 50)
                    end_idx = min(len(resume_lower), keyword_index + 50)
                    context = resume_text[start_idx:end_idx].replace('\n', ' ').strip()
                    
                    # Primary keyword gets higher score
                    if keyword == skill_name.lower():
                        skill_score = 90
                        evidence = f"Direct mention of {skill_name} in context: '...{context}...'"
                        break
                    else:
                        # Related keyword gets partial score
                        skill_score = 70
                        evidence = f"Related technology found ({keyword}) in context: '...{context}...'"
            
            # Weighted contribution to total score
            total_score += skill_score * importance_weight / 100
            
            if skill_score > 0:
                skill_matches.append({
                    "skill_name": skill_name,
                    "importance_weight": importance_weight,
                    "match_score": skill_score,
                    "evidence": evidence
                })
            else:
                missing_skills.append({
                    "skill_name": skill_name,
                    "importance_weight": importance_weight,
                    "improvement_suggestion": f"Consider adding experience with {skill_name} to your resume."
                })
        
        # Calculate overall score
        overall_match_score = int(total_score / (total_weight / 100)) if total_weight > 0 else 70
        
        # Generate generic strengths based on skills matched
        strengths = []
        if skill_matches:
            for match in skill_matches[:3]:  # Use top 3 skills as strengths
                strengths.append(f"Strong background in {match['skill_name']}")
        else:
            strengths = ["Technical background present but couldn't analyze details"]
        
        # Generate improvement areas
        improvement_areas = []
        for missing in missing_skills[:3]:
            improvement_areas.append(f"Develop skills in {missing['skill_name']}")
        
        if not improvement_areas:
            improvement_areas = ["Consider enhancing your resume with more specific accomplishments"]
        
        # Detailed feedback
        if missing_skills:
            missing_skill_names = ", ".join([s["skill_name"] for s in missing_skills])
            detailed_feedback = f"Your resume shows strength in {', '.join([m['skill_name'] for m in skill_matches[:2]])} but could benefit from adding experience with {missing_skill_names}."
        else:
            detailed_feedback = "Your resume shows a good match for this position. Consider highlighting specific achievements to stand out further."
        
        return {
            "overall_match_score": overall_match_score,
            "skill_matches": skill_matches,
            "missing_skills": missing_skills,
            "strengths": strengths,
            "improvement_areas": improvement_areas,
            "detailed_feedback": detailed_feedback,
            "score_note": "Score was calculated using our fallback algorithm. This provides a reasonable estimate but may be less precise than our AI-powered analysis."
        }
        
    except Exception as e:
        print(f"Error in fallback_analyze_job_application: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return a truly last-resort response if everything fails
        return {
            "overall_match_score": 75,  # More balanced default score
            "skill_matches": [],
            "missing_skills": [],
            "strengths": ["Technical background present but couldn't analyze details"],
            "improvement_areas": ["Consider formatting resume for better parsing"],
            "detailed_feedback": "We encountered an issue analyzing your resume in detail, but your background appears relevant. For more accurate matching, ensure your resume clearly lists your technical skills and experience."
        }

@app.route('/api/analyze-application', methods=['POST'])
def analyze_application():
    """API endpoint to analyze a job application."""
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        required_fields = ['application_id', 'job_id']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        application_id = data['application_id']
        job_id = data['job_id']
        
        print(f"Beginning analysis for application {application_id} for job {job_id}")
        
        # Fetch application from database
        try:
            application = db.applications.find_one({"_id": ObjectId(application_id)})
        except Exception as e:
            print(f"Error converting to ObjectId: {str(e)}")
            return jsonify({"error": f"Invalid application ID format: {application_id}"}), 400
            
        if not application:
            print(f"Application not found: {application_id}")
            return jsonify({"error": "Application not found"}), 404
        
        # Fetch job from database
        try:
            job = db.jobs.find_one({"_id": ObjectId(job_id)})
        except Exception as e:
            print(f"Error converting to ObjectId: {str(e)}")
            return jsonify({"error": f"Invalid job ID format: {job_id}"}), 400
            
        if not job:
            print(f"Job not found: {job_id}")
            return jsonify({"error": "Job not found"}), 404
        
        # Extract text from resume
        print(f"Extracting text from resume for application {application_id}")
        resume_data = application.get('resumeData', '')
        resume_text = extract_text_from_resume(resume_data)
        
        if not resume_text or resume_text == "Error extracting text from resume":
            print(f"Failed to extract text from resume for application {application_id}. Creating default analysis.")
            analysis_result = {
                "overall_match_score": 70,  # Default to a more positive score
                "skill_matches": [],
                "missing_skills": [],
                "strengths": ["Unable to determine specific strengths due to resume processing issues"],
                "improvement_areas": ["Please ensure your resume is properly formatted"],
                "detailed_feedback": "We couldn't analyze your resume in detail, but we've assigned a provisional score. Please ensure your resume is in a standard format (PDF, DOCX) for better results."
            }
        else:
            # Get job description and skills
            job_description = job.get('description', '')
            required_skills = job.get('skills', [])
            
            print(f"Resume text extracted successfully, length: {len(resume_text)} characters")
            
            # If no skills were provided in the job, create a reasonable default
            if not required_skills or len(required_skills) == 0:
                print(f"No skills found for job {job_id}. Creating default skill requirements.")
                job_title = job.get('title', '').lower()
                
                # Extract likely skills from job title
                if "developer" in job_title or "engineer" in job_title:
                    if "front" in job_title:
                        required_skills = [
                            {"name": "HTML/CSS", "weight": 80},
                            {"name": "JavaScript", "weight": 90}
                        ]
                    elif "back" in job_title:
                        required_skills = [
                            {"name": "Server-side programming", "weight": 90},
                            {"name": "Database skills", "weight": 80}
                        ]
                    elif "full" in job_title:
                        required_skills = [
                            {"name": "Frontend technologies", "weight": 80},
                            {"name": "Backend technologies", "weight": 80}
                        ]
                    else:
                        required_skills = [
                            {"name": "Programming skills", "weight": 90},
                            {"name": "Problem solving", "weight": 80}
                        ]
            
            # Analyze the application
            print(f"Starting analysis with {len(required_skills)} required skills")
            analysis_result = analyze_job_application(resume_text, job_description, required_skills)
            print(f"Analysis complete. Overall match score: {analysis_result.get('overall_match_score', 0)}")
        
        # Save analysis result to the application
        try:
            db.applications.update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "analysis": analysis_result,
                        "matchScore": analysis_result.get("overall_match_score", 0),
                        "analyzed_at": datetime.datetime.utcnow()
                    }
                }
            )
            print(f"Successfully saved analysis result for application {application_id}")
        except Exception as e:
            print(f"Error saving analysis result: {str(e)}")
            # Continue and return the result even if we couldn't save it
        
        return jsonify({
            "success": True,
            "analysis": analysis_result
        }), 200
    
    except Exception as e:
        print(f"Error analyzing application: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to analyze application: {str(e)}"}), 500

@app.route('/api/update-application-status', methods=['POST'])
def update_application_status():
    """API endpoint to update application status and send feedback."""
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        required_fields = ['application_id', 'status', 'notes']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        application_id = data['application_id']
        new_status = data['status']
        recruiter_notes = data['notes']
        
        print(f"Processing status update for application: {application_id}")
        
        # Fetch application from database
        try:
            application = db.applications.find_one({"_id": ObjectId(application_id)})
        except Exception as e:
            print(f"Error converting to ObjectId: {str(e)}")
            return jsonify({"error": f"Invalid application ID format: {application_id}"}), 400
            
        if not application:
            return jsonify({"error": "Application not found"}), 404
        
        print(f"Found application: {application.get('applicantName', 'Unknown')} for job: {application.get('jobTitle', 'Unknown')}")
        
        # Update application status
        db.applications.update_one(
            {"_id": ObjectId(application_id)},
            {
                "$set": {
                    "status": new_status,
                    "notes": recruiter_notes,
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        
        # Generate feedback based on status
        if new_status == "rejected":
            # Generate a personalized rejection feedback using Gemini
            analysis = application.get("analysis", {})
            missing_skills = analysis.get("missing_skills", [])
            improvement_areas = analysis.get("improvement_areas", [])
            
            prompt = f"""
            You're a helpful recruitment AI sending a rejection feedback email to a candidate.
            
            The candidate applied for the position: {application.get('jobTitle', 'the position')}
            
            Their application was rejected for the following reasons:
            - Missing skills: {", ".join([skill.get("skill_name", "") for skill in missing_skills])}
            - Areas for improvement: {", ".join(improvement_areas)}
            - Recruiter notes: {recruiter_notes}
            
            Write a polite, constructive, and empathetic feedback message (150-200 words) to the candidate explaining:
            1. Thank them for their application
            2. Gently explain that they weren't selected
            3. Provide constructive feedback on missing skills and how they could improve
            4. Encourage them for future opportunities
            
            Keep the tone professional, kind, and helpful. Don't be overly negative or discouraging.
            """
            
            response = model.generate_content(prompt)
            feedback = response.text
            
            # Save the feedback
            db.applications.update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "rejection_feedback": feedback
                    }
                }
            )
            
            # Here you would normally send an email to the candidate
            # For now we'll just return the feedback
            return jsonify({
                "success": True,
                "status": new_status,
                "feedback": feedback
            }), 200
        
        elif new_status == "shortlisted":
            # Generate acceptance feedback
            prompt = f"""
            You're a helpful recruitment AI sending a positive feedback email to a candidate.
            
            The candidate applied for the position: {application.get('jobTitle', 'the position')}
            
            Their application was shortlisted with these recruiter notes:
            {recruiter_notes}
            
            Write a brief, professional, and encouraging message (100-150 words) to the candidate:
            1. Thank them for their application
            2. Inform them they've been shortlisted
            3. Explain the next steps in the process
            4. Mention that someone from the recruitment team will contact them soon
            
            Keep the tone professional but warm and positive.
            """
            
            response = model.generate_content(prompt)
            feedback = response.text
            
            # Save the feedback
            db.applications.update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "acceptance_feedback": feedback
                    }
                }
            )
            
            # Here you would normally send an email to the candidate
            return jsonify({
                "success": True,
                "status": new_status,
                "feedback": feedback
            }), 200
        
        else:
            # For other statuses, just return success
            return jsonify({
                "success": True,
                "status": new_status
            }), 200
    
    except Exception as e:
        print(f"Error updating application status: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to update application status: {str(e)}"}), 500

@app.route('/api/get-application-feedback', methods=['GET'])
def get_application_feedback():
    """API endpoint for applicants to check their application status and feedback."""
    try:
        application_id = request.args.get('application_id')
        if not application_id:
            return jsonify({"error": "Application ID is required"}), 400
        
        # Fetch application from database
        try:
            application = db.applications.find_one({"_id": ObjectId(application_id)})
        except Exception as e:
            print(f"Error converting to ObjectId: {str(e)}")
            return jsonify({"error": f"Invalid application ID format: {application_id}"}), 400
            
        if not application:
            return jsonify({"error": "Application not found"}), 404
        
        # Prepare response based on status
        status = application.get("status", "pending")
        response_data = {
            "status": status,
            "jobTitle": application.get("jobTitle", ""),
            "companyName": application.get("companyName", ""),
            "appliedAt": application.get("created_at"),
            "updatedAt": application.get("updated_at")
        }
        
        if status == "rejected" and "rejection_feedback" in application:
            response_data["feedback"] = application["rejection_feedback"]
            
            # Add improvement suggestions from analysis
            if "analysis" in application:
                analysis = application["analysis"]
                response_data["match_score"] = analysis.get("overall_match_score", 0)
                response_data["missing_skills"] = analysis.get("missing_skills", [])
                response_data["improvement_areas"] = analysis.get("improvement_areas", [])
        
        elif status == "shortlisted" and "acceptance_feedback" in application:
            response_data["feedback"] = application["acceptance_feedback"]
            
            # Add strengths from analysis
            if "analysis" in application:
                analysis = application["analysis"]
                response_data["match_score"] = analysis.get("overall_match_score", 0)
                response_data["strengths"] = analysis.get("strengths", [])
        
        return jsonify({
            "success": True,
            "application": response_data
        }), 200
    
    except Exception as e:
        print(f"Error getting application feedback: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to get application feedback: {str(e)}"}), 500

@app.route('/api/reanalyze-job-applications', methods=['POST'])
def reanalyze_job_applications():
    """API endpoint to reanalyze all applications for a specific job."""
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        if 'job_id' not in data:
            return jsonify({"error": "Job ID is required"}), 400
        
        job_id = data['job_id']
        
        print(f"Reanalyzing all applications for job {job_id}")
        
        # Fetch job from database
        try:
            job = db.jobs.find_one({"_id": ObjectId(job_id)})
        except Exception as e:
            print(f"Error converting to ObjectId: {str(e)}")
            return jsonify({"error": f"Invalid job ID format: {job_id}"}), 400
            
        if not job:
            return jsonify({"error": "Job not found"}), 404
        
        # Get job description and skills
        job_description = job.get('description', '')
        required_skills = job.get('skills', [])
        
        # Fetch all applications for this job
        applications = list(db.applications.find({"jobId": job_id}))
        
        if not applications:
            return jsonify({"message": "No applications found for this job"}), 200
        
        updated_applications = 0
        results = []
        
        # Process each application
        for application in applications:
            try:
                application_id = str(application.get("_id"))
                print(f"Reanalyzing application {application_id}")
                
                # Extract text from resume
                resume_data = application.get('resumeData', '')
                resume_text = extract_text_from_resume(resume_data)
                
                if not resume_text or resume_text == "Error extracting text from resume":
                    print(f"Failed to extract text from resume for application {application_id}")
                    continue
                
                # Analyze the application
                analysis_result = analyze_job_application(resume_text, job_description, required_skills)
                
                # Save updated analysis result
                db.applications.update_one(
                    {"_id": application.get("_id")},
                    {
                        "$set": {
                            "analysis": analysis_result,
                            "matchScore": analysis_result.get("overall_match_score", 0),
                            "reanalyzed_at": datetime.datetime.utcnow()
                        }
                    }
                )
                
                updated_applications += 1
                results.append({
                    "application_id": application_id,
                    "applicant_name": application.get("applicantName", "Unknown"),
                    "previous_score": application.get("matchScore", 0),
                    "new_score": analysis_result.get("overall_match_score", 0)
                })
                
            except Exception as e:
                print(f"Error reanalyzing application {application.get('_id')}: {str(e)}")
        
        return jsonify({
            "success": True,
            "message": f"Reanalyzed {updated_applications} applications",
            "results": results
        }), 200
    
    except Exception as e:
        print(f"Error reanalyzing applications: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to reanalyze applications: {str(e)}"}), 500

if __name__ == "__main__":
    # Check if Gemini API key is valid
    api_available = False
    try:
        print("Checking connection to Gemini API...")
        test_response = model.generate_content("Hello, please respond with just the word 'Connected' to verify the connection.")
        if "Connected" in test_response.text:
            print("✓ Successfully connected to Gemini API")
            api_available = True
        else:
            print("⚠️ Connected to Gemini API but received unexpected response")
            print("⚠️ Fallback matching will be used for job applications")
    except Exception as e:
        print(f"⚠️ Error connecting to Gemini API: {str(e)}")
        print("⚠️ Fallback matching will be used for job applications")
    
    if not api_available:
        print("🔄 Job matching will use rule-based analysis instead of AI")
        print("💡 To use AI matching, please check your Google API key and quota")
    
    # Start the Flask app even if the API isn't available
    app.run(debug=True, port=5002) 