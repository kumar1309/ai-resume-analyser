import os
from dotenv import load_dotenv
import google.generativeai as genai
from PyPDF2 import PdfReader
from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import json

# Load environment variables and configure API
load_dotenv()

# Get API key from environment
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set")

# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)

# Set default model configuration
generation_config = {
    "temperature": 0.2,  # Lower temperature for more consistent outputs
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
}

# Initialize model
model = genai.GenerativeModel(
    model_name="gemini-1.5-pro", 
    generation_config=generation_config
)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Function to get Gemini output
def get_gemini_output(pdf_text, prompt):
    try:
        # Configure the model with the latest settings
        generation_config = {
            "temperature": 0.2,  # Lower temperature for more consistent outputs
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
        }
        
        # Always reinitialize the model to use the latest API key
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            generation_config=generation_config
        )
        
        response = model.generate_content([pdf_text, prompt])
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API: {str(e)}")
        # If we still encounter an error, don't use the marker - re-raise to get proper error
        raise

# Function to extract skills from resume
def extract_skills(resume_text, job_description=None):
    # If no job description, just extract skills from resume
    if not job_description:
        try:
            # Use Gemini to extract skills from resume
            prompt = f"""
            Analyze this resume and extract all technical skills mentioned.
            Return ONLY a JSON array of skill objects in this format:
            [
                {{"skill": "Skill Name", "score": 85}},
                {{"skill": "Another Skill", "score": 78}}
            ]
            
            The score should be between 70-95 based on how prominently the skill appears in the resume.
            Limit to the top 5-7 most relevant skills.
            
            Resume text: {resume_text}
            """
            
            skills_response = get_gemini_output("", prompt)
            
            # Extract JSON from response
            try:
                # Find JSON in the response (might be surrounded by backticks or other text)
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', skills_response)
                if json_match:
                    skills_json = json_match.group(1)
                else:
                    # Try to find JSON without backticks
                    json_match = re.search(r'\[\s*{\s*"skill":', skills_response)
                    if json_match:
                        skills_json = skills_response[json_match.start():]
                    else:
                        skills_json = skills_response
                
                # Parse JSON
                skills_data = json.loads(skills_json)
                return skills_data[:5]  # Return top 5 skills
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing skills from resume: {e}")
                print(f"Response was: {skills_response}")
                # Fallback to simple regex extraction
                return fallback_skill_extraction(resume_text)
        except Exception as e:
            print(f"Error using Gemini for skill extraction: {e}")
            return fallback_skill_extraction(resume_text)
    
    # If job description is provided, match skills
    else:
        try:
            # Use Gemini to match resume skills with job requirements
            prompt = f"""
            You are an expert ATS (Applicant Tracking System) analyzer.
            
            First, extract all technical skills from this job description for a {detect_job_role(job_description)} position.
            
            Then, analyze the resume and identify which skills from the job description are present in the resume.
            Also identify additional relevant skills in the resume that might be valuable for this position.
            
            Return ONLY a JSON array of skill objects in this format:
            [
                {{"skill": "Skill Name", "score": 88, "jobMatch": true}},
                {{"skill": "Another Skill", "score": 75, "jobMatch": false}}
            ]
            
            Rules:
            - The "score" should be between 70-95
            - Give higher scores (85-95) to skills that match the job requirements
            - Give lower scores (70-84) to skills that are in the resume but not specifically mentioned in the job
            - The "jobMatch" boolean should be true if the skill is mentioned in the job description
            - Focus only on the most relevant 5-7 skills for this specific job role
            - Prioritize skills that are actually in the resume, don't make them up
            - For UI/UX roles, focus on design tools, research methods and design principles
            - For cloud engineering roles, focus on cloud platforms, infrastructure and DevOps skills
            - For data science roles, focus on ML/AI frameworks, statistical methods and data processing
            
            Job description: {job_description}
            
            Resume text: {resume_text}
            """
            
            skills_response = get_gemini_output("", prompt)
            
            # Extract JSON from response
            try:
                # Find JSON in the response
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', skills_response)
                if json_match:
                    skills_json = json_match.group(1)
                else:
                    # Try to find JSON without backticks
                    json_match = re.search(r'\[\s*{\s*"skill":', skills_response)
                    if json_match:
                        skills_json = skills_response[json_match.start():]
                    else:
                        skills_json = skills_response
                
                # Parse JSON
                skills_data = json.loads(skills_json)
                
                # Sort: job matches first (higher priority), then by score
                skills_data.sort(key=lambda x: (-x.get('jobMatch', False), -x.get('score', 0)))
                
                return skills_data[:5]  # Return top 5 skills
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing skills from job matching: {e}")
                print(f"Response was: {skills_response}")
                # Fallback
                return fallback_skill_job_matching(resume_text, job_description)
        except Exception as e:
            print(f"Error using Gemini for job skill matching: {e}")
            return fallback_skill_job_matching(resume_text, job_description)

# Helper function to detect job role from description
def detect_job_role(job_description):
    job_roles = {
        "UI/UX Designer": ["ui", "ux", "user interface", "user experience", "design", "designer", "figma", "sketch"],
        "Cloud Engineer": ["cloud", "aws", "azure", "gcp", "devops", "infrastructure"],
        "Frontend Developer": ["frontend", "front-end", "react", "angular", "vue", "ui developer"],
        "Backend Developer": ["backend", "back-end", "api", "server-side", "database"],
        "Full Stack Developer": ["full stack", "full-stack", "fullstack", "frontend", "backend"],
        "Data Scientist": ["data scientist", "machine learning", "ai", "ml", "data analysis"],
        "Mobile Developer": ["mobile", "ios", "android", "react native", "flutter"],
        "Product Manager": ["product manager", "product owner", "roadmap", "stakeholder"]
    }
    
    role_scores = {}
    description_lower = job_description.lower()
    
    for role, keywords in job_roles.items():
        score = 0
        for keyword in keywords:
            if keyword.lower() in description_lower:
                score += 1
        if score > 0:
            role_scores[role] = score
    
    if not role_scores:
        return "General"
    
    # Return the role with highest score
    return max(role_scores.items(), key=lambda x: x[1])[0]

# Fallback skill extraction when Gemini fails
def fallback_skill_extraction(resume_text):
    common_skills = [
        "HTML", "CSS", "JavaScript", "TypeScript", "Python", "Java", "C#", "SQL",
        "React", "Angular", "Vue", "Node.js", "Express", "Django", "Flask",
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Git", "Jenkins",
        "Figma", "Sketch", "Adobe XD", "Photoshop", "Illustrator",
        "User Research", "Wireframing", "Prototyping", "UI Design", "UX Design"
    ]
    
    skills_found = []
    for skill in common_skills:
        skill_pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(skill_pattern, resume_text, re.IGNORECASE):
            import random
            score = random.randint(70, 90)
            skills_found.append({"skill": skill, "score": score})
    
    # Sort by score
    skills_found.sort(key=lambda x: x["score"], reverse=True)
    return skills_found[:5]  # Return top 5 skills

# Fallback skill-job matching when Gemini fails
def fallback_skill_job_matching(resume_text, job_description):
    # Extract skills that appear in both resume and job description
    words_in_job = set(re.findall(r'\b\w+\b', job_description.lower()))
    
    # Common technical skills to look for
    common_skills = [
        "HTML", "CSS", "JavaScript", "TypeScript", "Python", "Java", "C#", "SQL",
        "React", "Angular", "Vue", "Node.js", "Express", "Django", "Flask",
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Git", "Jenkins",
        "Figma", "Sketch", "Adobe XD", "Photoshop", "Illustrator",
        "User Research", "Wireframing", "Prototyping", "UI Design", "UX Design"
    ]
    
    skills_found = []
    for skill in common_skills:
        skill_pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(skill_pattern, resume_text, re.IGNORECASE):
            import random
            # Check if skill is in job description
            skill_in_job = skill.lower() in words_in_job or any(word in skill.lower() for word in words_in_job)
            
            if skill_in_job:
                score = random.randint(85, 95)
                skills_found.append({"skill": skill, "score": score, "jobMatch": True})
            else:
                score = random.randint(70, 84)
                skills_found.append({"skill": skill, "score": score, "jobMatch": False})
    
    # Sort: job matches first, then by score
    skills_found.sort(key=lambda x: (-x.get("jobMatch", False), -x["score"]))
    return skills_found[:5]  # Return top 5 skills

# Function to read PDF
def read_pdf(file):
    try:
        pdf_reader = PdfReader(file)
        pdf_text = ""
        for page in pdf_reader.pages:
            pdf_text += page.extract_text()
        return pdf_text
    except Exception as e:
        return str(e)

# Process suggestions from Gemini's output
def process_suggestions(response_text):
    suggestions = []
    # Look for numbered suggestions, improvements, or bullet points
    lines = response_text.split('\n')
    for line in lines:
        # Check for lines that look like suggestions
        if re.search(r'^\d+\.\s+', line) or line.strip().startswith('•') or line.strip().startswith('-'):
            # Clean up the suggestion
            suggestion = re.sub(r'^\d+\.\s+|^•\s+|^-\s+', '', line).strip()
            if suggestion and len(suggestion) > 10:  # Avoid empty or very short items
                suggestions.append(suggestion)
    
    # If we couldn't find structured suggestions, extract sentences with recommendation language
    if not suggestions:
        recommendation_patterns = [
            r'(?:should|could|recommend|suggest|consider|add|include|improve)\s+[^.!?]*[.!?]',
            r'(?:missing|lacks|needs|requires)[^.!?]*[.!?]'
        ]
        for pattern in recommendation_patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            suggestions.extend([match.strip() for match in matches if len(match.strip()) > 10])
    
    # Limit to top 5 suggestions
    return suggestions[:5]

# Extract ATS score from Gemini's output
def extract_ats_score(response_text):
    # Try to find an ATS score in the response
    score_patterns = [
        r'ATS\s+(?:compatibility\s+)?score(?:\s+of)?\s*:?\s*(\d{1,3})(?:\s*\/\s*100|\s*%)?',
        r'(\d{1,3})(?:\s*\/\s*100|\s*%)?\s*ATS\s+(?:compatibility\s+)?score',
        r'ATS\s+(?:compatibility|score)(?:\s+is)?\s*:?\s*(\d{1,3})(?:\s*\/\s*100|\s*%)?'
    ]
    
    for pattern in score_patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            try:
                score = int(match.group(1))
                # Ensure the score is within reasonable bounds
                if 0 <= score <= 100:
                    return score
            except ValueError:
                pass
    
    # Default score if no match found
    return 75  # A reasonable default

# Generate skill development recommendations
def generate_skill_recommendations(resume_text, job_description=None):
    # Default recommendations if we can't get them from Gemini
    default_recommendations = [
        {
            "skill": "React",
            "why": "Essential for modern frontend development",
            "courses": [
                {"title": "React - The Complete Guide", "platform": "Udemy", "url": "https://www.udemy.com/course/react-the-complete-guide-incl-redux/"},
                {"title": "Modern React with Redux", "platform": "Udemy", "url": "https://www.udemy.com/course/react-redux/"}
            ]
        },
        {
            "skill": "Python",
            "why": "Versatile programming language for data science and backend",
            "courses": [
                {"title": "Complete Python Bootcamp", "platform": "Udemy", "url": "https://www.udemy.com/course/complete-python-bootcamp/"},
                {"title": "Python for Everybody", "platform": "Coursera", "url": "https://www.coursera.org/specializations/python"}
            ]
        },
        {
            "skill": "SQL",
            "why": "Data management is crucial for all developers",
            "courses": [
                {"title": "The Complete SQL Bootcamp", "platform": "Udemy", "url": "https://www.udemy.com/course/the-complete-sql-bootcamp/"},
                {"title": "SQL for Data Science", "platform": "Coursera", "url": "https://www.coursera.org/learn/sql-for-data-science"}
            ]
        }
    ]
    
    try:
        # Prepare a prompt for Gemini to get skill recommendations
        prompt = f"""
        You are a career advisor specializing in tech careers. Based on the following resume and job description, 
        suggest 3-5 skills the candidate should develop to improve their career prospects.
        
        For each skill:
        1. Name the skill
        2. Explain why it's important (1-2 sentences)
        3. Suggest 2 specific courses or resources to learn this skill
        
        Format your response as a JSON array with this structure:
        [
            {{
                "skill": "Skill Name",
                "why": "Brief explanation of importance",
                "courses": [
                    {{ "title": "Course Title 1", "platform": "Platform Name", "url": "course_url" }},
                    {{ "title": "Course Title 2", "platform": "Platform Name", "url": "course_url" }}
                ]
            }}
        ]
        
        Resume text: {resume_text}
        Job description (if provided): {job_description}
        """
        
        # Get recommendations from Gemini
        response = get_gemini_output(resume_text, prompt)
        
        # Try to extract JSON from the response
        try:
            # Find JSON in the response (it might be surrounded by backticks or other text)
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without backticks
                json_match = re.search(r'\[\s*{\s*"skill":', response)
                if json_match:
                    json_str = response[json_match.start():]
                else:
                    json_str = response
            
            # Parse the JSON
            recommendations = json.loads(json_str)
            
            # Validate the structure
            for rec in recommendations:
                if not all(key in rec for key in ["skill", "why", "courses"]):
                    raise ValueError("Invalid recommendation structure")
            
            return recommendations
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing skill recommendations: {e}")
            print(f"Response was: {response}")
            return default_recommendations
    except Exception as e:
        print(f"Error generating skill recommendations: {e}")
        return default_recommendations

@app.route('/api/analyze-resume', methods=['POST'])
def analyze_resume():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not file.filename.endswith('.pdf'):
        return jsonify({"error": "Only PDF files are supported"}), 400
    
    job_description = request.form.get('jobDescription', '')
    analysis_type = request.form.get('analysisType', 'quick')
    
    try:
        pdf_text = read_pdf(file)
        if not pdf_text or len(pdf_text) < 50:
            return jsonify({"error": "Could not extract text from PDF or PDF has insufficient content"}), 400
        
        # Detect job role from job description if available
        job_role = "general"
        if job_description:
            # Check for common job roles in the description
            job_roles = {
                "cloud engineer": ["cloud engineer", "cloud infrastructure", "aws engineer", "azure engineer", "gcp engineer", "cloud architect"],
                "frontend developer": ["frontend", "front-end", "react", "angular", "vue", "ui developer"],
                "backend developer": ["backend", "back-end", "api developer", "server-side"],
                "full stack": ["full stack", "full-stack", "fullstack"],
                "data scientist": ["data scientist", "machine learning", "ai engineer", "ml engineer"],
                "devops": ["devops", "sre", "site reliability", "platform engineer"],
                "mobile developer": ["mobile developer", "ios developer", "android developer", "react native"],
                "security engineer": ["security engineer", "cybersecurity", "information security"]
            }
            
            # Find which role the job description best matches
            for role, keywords in job_roles.items():
                if any(keyword.lower() in job_description.lower() for keyword in keywords):
                    job_role = role
                    break
        
        prompt_prefix = ""
        if job_role == "cloud engineer":
            prompt_prefix = """
            As an expert in cloud engineering resume evaluation, focus on these areas:
            - Experience with cloud platforms (AWS, Azure, GCP)
            - Infrastructure as Code skills (Terraform, CloudFormation)
            - Containerization (Docker, Kubernetes)
            - CI/CD pipelines and automation
            - Cloud security and networking concepts
            - Monitoring and logging solutions
            """
        elif job_role == "frontend developer":
            prompt_prefix = """
            As an expert in frontend development resume evaluation, focus on these areas:
            - Modern JavaScript frameworks (React, Angular, Vue)
            - CSS and styling approaches (Sass, styled-components)
            - State management (Redux, Context API)
            - Performance optimization techniques
            - Responsive design principles
            - Web accessibility knowledge
            """
        elif job_role == "data scientist":
            prompt_prefix = """
            As an expert in data science resume evaluation, focus on these areas:
            - Machine learning frameworks and libraries
            - Data analysis and visualization tools
            - Statistical analysis experience
            - Big data technologies
            - Domain expertise in relevant fields
            - Project examples showing ML application
            """
        
        if analysis_type == 'quick':
            prompt = f"""
            {prompt_prefix}
            You are ResumeChecker, an expert in resume analysis. Provide a quick scan of the following resume:
            
            1. Identify the most suitable profession for this resume.
            2. List 3 key strengths of the resume.
            3. Suggest 2 quick improvements.
            4. Give an overall ATS score out of 100. Make sure to evaluate properly and VARY the score based on the resume quality, avoid giving the same score to all resumes.
            
            Resume text: {pdf_text}
            Job description (if provided): {job_description}
            """
        elif analysis_type == 'detailed':
            prompt = f"""
            {prompt_prefix}
            You are ResumeChecker, an expert in resume analysis. Provide a detailed analysis of the following resume:
            
            1. Identify the most suitable profession for this resume.
            2. List 5 strengths of the resume.
            3. Suggest 3-5 areas for improvement with specific recommendations.
            4. Rate the following aspects out of 10: Impact, Brevity, Style, Structure, Skills.
            5. Provide a brief review of each major section (e.g., Summary, Experience, Education).
            6. Give an overall ATS score out of 100 with a breakdown of the scoring. Make sure to evaluate properly and VARY the score based on the resume quality, avoid giving the same score to all resumes.
            
            Resume text: {pdf_text}
            Job description (if provided): {job_description}
            """
        else:  # ATS Optimization
            prompt = f"""
            {prompt_prefix}
            You are ResumeChecker, an expert in ATS optimization. Analyze the following resume and provide optimization suggestions:
            
            1. Identify keywords from the job description that should be included in the resume.
            2. Suggest reformatting or restructuring to improve ATS readability.
            3. Recommend changes to improve keyword density without keyword stuffing.
            4. Provide 3-5 bullet points on how to tailor this resume for the specific job description.
            5. Give an ATS compatibility score out of 100 and explain how to improve it. Make sure to evaluate properly and VARY the score based on the resume quality, avoid giving the same score to all resumes.
            
            Resume text: {pdf_text}
            Job description: {job_description}
            """
        
        # Force direct API call - no fallbacks
        response = get_gemini_output(pdf_text, prompt)
        
        # Extract structured data from the response
        ats_score = extract_ats_score(response)
        skill_matches = extract_skills(pdf_text, job_description)
        suggestions = process_suggestions(response)
        skill_recommendations = generate_skill_recommendations(pdf_text, job_description)
        
        return jsonify({
            "success": True,
            "atsScore": ats_score,
            "skillMatches": skill_matches,
            "suggestions": suggestions,
            "skillRecommendations": skill_recommendations,
            "fullAnalysis": response,  # Include the full text for reference
            "jobRole": job_role,  # Include detected job role for reference
            "jobDescription": job_description  # Include the job description
        })
        
    except Exception as e:
        print(f"Error in analyze_resume: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to analyze resume: {str(e)}. Please try again."}), 500

@app.route('/api/skill-recommendations', methods=['POST'])
def skill_recommendations():
    if 'resumeText' not in request.json:
        return jsonify({"error": "No resume text provided"}), 400
    
    resume_text = request.json.get('resumeText')
    job_description = request.json.get('jobDescription', '')
    
    try:
        recommendations = generate_skill_recommendations(resume_text, job_description)
        
        # Check if we received a valid response
        if not recommendations or len(recommendations) == 0:
            # Use default recommendations
            recommendations = [
                {
                    "skill": "Resume Formatting",
                    "why": "ATS systems need to properly parse your resume",
                    "courses": [
                        {"title": "ATS-Friendly Resume Building", "platform": "LinkedIn Learning", "url": "https://www.linkedin.com/learning/"},
                        {"title": "Resume Writing for Tech Professionals", "platform": "Udemy", "url": "https://www.udemy.com/"}
                    ]
                },
                {
                    "skill": "Job-Specific Keywords",
                    "why": "Incorporate relevant keywords from job descriptions",
                    "courses": [
                        {"title": "Keyword Optimization for Job Applications", "platform": "Coursera", "url": "https://www.coursera.org/"},
                        {"title": "SEO Principles for Job Seekers", "platform": "Udemy", "url": "https://www.udemy.com/"}
                    ]
                },
                {
                    "skill": "Technical Skill Development",
                    "why": "Keep your technical skills current and relevant",
                    "courses": [
                        {"title": "Full Stack Web Development", "platform": "Udemy", "url": "https://www.udemy.com/"},
                        {"title": "Cloud Certification Paths", "platform": "A Cloud Guru", "url": "https://acloudguru.com/"}
                    ]
                }
            ]
        
        return jsonify({
            "success": True,
            "recommendations": recommendations
        })
    except Exception as e:
        print(f"Error in skill_recommendations: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to generate skill recommendations. Please try again."}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
