from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, verify_jwt_in_request, current_user
import bcrypt
import os
import datetime
from datetime import timedelta
from bson.objectid import ObjectId
import json

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Configure maximum request size for large profile images
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max size

# Configure MongoDB
app.config["MONGO_URI"] = "mongodb://localhost:27017/jobmatchdb"
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "your-secret-key-change-in-production")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"

mongo = PyMongo(app)
jwt = JWTManager(app)

# Fix for complex identity claims
@jwt.user_identity_loader
def user_identity_lookup(user):
    if isinstance(user, dict):
        return json.dumps(user)
    return user

@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    try:
        if isinstance(identity, str) and identity.startswith('{'):
            return json.loads(identity)
        return identity
    except:
        return identity

# User registration
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    
    # Validate input
    if not data or not data.get("email") or not data.get("password") or not data.get("role"):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Check if email already exists
    if mongo.db.users.find_one({"email": data["email"]}):
        return jsonify({"error": "Email already exists"}), 400
    
    # Hash password
    hashed_password = bcrypt.hashpw(data["password"].encode("utf-8"), bcrypt.gensalt())
    
    # Create user document
    user = {
        "email": data["email"],
        "password": hashed_password,
        "role": data["role"],
        "name": data.get("name", ""),
        "created_at": datetime.datetime.utcnow()
    }
    
    # Insert into MongoDB
    mongo.db.users.insert_one(user)
    
    # Create JWT token
    access_token = create_access_token(
        identity={
            "email": user["email"],
            "role": user["role"],
            "userId": str(user["_id"])
        }
    )
    
    return jsonify({
        "success": True,
        "token": access_token,
        "user": {
            "email": user["email"],
            "role": user["role"],
            "name": user["name"]
        }
    }), 201

# User login
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    
    # Validate input
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "Missing email or password"}), 400
    
    # Find user by email
    user = mongo.db.users.find_one({"email": data["email"]})
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    
    # Check password
    if not bcrypt.checkpw(data["password"].encode("utf-8"), user["password"]):
        return jsonify({"error": "Invalid credentials"}), 401
    
    # Create JWT token
    access_token = create_access_token(
        identity={
            "email": user["email"],
            "role": user["role"],
            "userId": str(user["_id"])
        }
    )
    
    return jsonify({
        "success": True,
        "token": access_token,
        "user": {
            "email": user["email"],
            "role": user["role"],
            "name": user.get("name", "")
        }
    }), 200

# Get current user
@app.route("/api/user", methods=["GET"])
@jwt_required()
def get_user():
    try:
        current_user_identity = get_jwt_identity()
        print(f"Current user from JWT (raw): {current_user_identity}")
        
        # Handle string or dict identity
        if isinstance(current_user_identity, str) and current_user_identity.startswith('{'):
            try:
                current_user_dict = json.loads(current_user_identity)
                print(f"Parsed user identity: {current_user_dict}")
                email = current_user_dict.get("email")
            except:
                print("Failed to parse JSON identity")
                email = current_user_identity
        elif isinstance(current_user_identity, dict):
            email = current_user_identity.get("email")
            print(f"Using dictionary identity with email: {email}")
        else:
            email = current_user_identity
            print(f"Using string identity: {email}")
            
        if not email:
            return jsonify({"error": "Invalid user identity"}), 400
        
        # Find user by email
        user = mongo.db.users.find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        return jsonify({
            "email": user["email"],
            "role": user["role"],
            "name": user.get("name", "")
        }), 200
    except Exception as e:
        print(f"Error in get_user: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to get user: {str(e)}"}), 500

# Get user profile
@app.route("/api/profile", methods=["GET"])
@jwt_required()
def get_profile():
    try:
        # Debug authorization header
        auth_header = request.headers.get('Authorization', '')
        print(f"Auth header: {auth_header}")
        
        current_user_identity = get_jwt_identity()
        print(f"Current user from JWT (raw): {current_user_identity}")
        
        # Handle string or dict identity
        if isinstance(current_user_identity, str) and current_user_identity.startswith('{'):
            try:
                current_user_dict = json.loads(current_user_identity)
                print(f"Parsed user identity: {current_user_dict}")
                email = current_user_dict.get("email")
            except:
                print("Failed to parse JSON identity")
                email = current_user_identity
        elif isinstance(current_user_identity, dict):
            email = current_user_identity.get("email")
            print(f"Using dictionary identity with email: {email}")
        else:
            email = current_user_identity
            print(f"Using string identity: {email}")
        
        if not email:
            return jsonify({"error": "Invalid user identity"}), 400
        
        # Find user by email
        user = mongo.db.users.find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        print(f"Found user with ID: {user['_id']}")
        
        # Get profile from profiles collection or create empty profile
        profile = mongo.db.profiles.find_one({"userId": str(user["_id"])})
        
        if not profile:
            # Return empty profile
            print(f"No profile found for user, returning empty profile")
            return jsonify({
                "userId": str(user["_id"]),
                "name": user.get("name", ""),
                "email": user["email"],
                "location": "",
                "bio": "",
                "profileImage": "",
                "experiences": [],
                "education": []
            }), 200
        
        # Remove MongoDB _id field for JSON serialization
        profile["_id"] = str(profile["_id"])
        print(f"Returning existing profile")
        
        return jsonify(profile), 200
    except Exception as e:
        print(f"Error in get_profile: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to get profile: {str(e)}"}), 500

# Create or update user profile
@app.route("/api/profile", methods=["POST"])
@jwt_required()
def update_profile():
    try:
        # Debug authorization header
        auth_header = request.headers.get('Authorization', '')
        print(f"Auth header: {auth_header}")
        
        current_user_identity = get_jwt_identity()
        print(f"Current user from JWT (raw): {current_user_identity}")
        
        # Handle string or dict identity
        if isinstance(current_user_identity, str) and current_user_identity.startswith('{'):
            try:
                current_user_dict = json.loads(current_user_identity)
                print(f"Parsed user identity: {current_user_dict}")
                email = current_user_dict.get("email")
            except:
                print("Failed to parse JSON identity")
                email = current_user_identity
        elif isinstance(current_user_identity, dict):
            email = current_user_identity.get("email")
            print(f"Using dictionary identity with email: {email}")
        else:
            email = current_user_identity
            print(f"Using string identity: {email}")
        
        if not email:
            return jsonify({"error": "Invalid user identity"}), 400
            
        # Debug request info
        print(f"Request content type: {request.content_type}")
        print(f"Request headers: {request.headers}")
        
        # Handle different content types
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json(silent=True)
        else:
            # Try to parse data even if content type isn't correct
            try:
                data = request.get_json(force=True, silent=True)
                print("Forced JSON parsing")
            except Exception as e:
                print(f"Failed to parse JSON: {str(e)}")
                data = request.form.to_dict() if request.form else {}
                print(f"Using form data instead: {data}")
        
        if not data:
            print("No data received or couldn't parse data")
            return jsonify({"error": "No profile data received or could not parse request"}), 400
            
        print(f"Received profile data: {data}")
        
        # Find user by email
        user = mongo.db.users.find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        print(f"Found user with ID: {user['_id']}")
        
        # Update user's name in users collection
        if data.get("name"):
            mongo.db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"name": data["name"]}}
            )
            print(f"Updated user name to: {data['name']}")
        
        # Create profile object - ensure all fields have proper default values
        profile = {
            "userId": str(user["_id"]),
            "name": data.get("name", user.get("name", "")),
            "email": user["email"],
            "location": data.get("location", ""),
            "bio": data.get("bio", ""),
            "profileImage": data.get("profileImage", ""),
            "experiences": data.get("experiences", []),
            "education": data.get("education", []),
            "updated_at": datetime.datetime.utcnow()
        }
        
        # Ensure experiences and education are lists even if they're somehow None or invalid
        if not isinstance(profile["experiences"], list):
            profile["experiences"] = []
        
        if not isinstance(profile["education"], list):
            profile["education"] = []
        
        # Upsert profile in profiles collection
        result = mongo.db.profiles.update_one(
            {"userId": str(user["_id"])},
            {"$set": profile},
            upsert=True
        )
        
        # Confirmation of success
        print(f"Profile updated successfully for user {user['email']}")
        return jsonify({
            "success": True,
            "message": "Profile updated successfully",
            "profile": profile
        }), 200
    
    except Exception as e:
        print(f"Error updating profile: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to update profile: {str(e)}"}), 500

# Handle JWT errors
@app.errorhandler(422)
def handle_unprocessable_entity(err):
    print(f"JWT Error: 422 Unprocessable Entity - {str(err)}")
    return jsonify({
        "error": "Invalid or expired token. Please login again.",
        "message": str(err)
    }), 422

@jwt.invalid_token_loader
def invalid_token_callback(error_string):
    print(f"Invalid token: {error_string}")
    return jsonify({
        'error': 'Invalid token',
        'message': error_string
    }), 401

@jwt.unauthorized_loader
def unauthorized_callback(error_string):
    print(f"Missing token: {error_string}")
    return jsonify({
        'error': 'Authorization required',
        'message': error_string
    }), 401

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    print(f"Expired token: {jwt_payload}")
    return jsonify({
        'error': 'Token has expired',
        'message': 'Please login again'
    }), 401

# Create a new job posting
@app.route("/api/jobs", methods=["POST"])
@jwt_required()
def create_job():
    try:
        # Get current user identity
        current_user_identity = get_jwt_identity()
        print(f"Current user from JWT (raw): {current_user_identity}")
        
        # Parse user identity
        if isinstance(current_user_identity, str) and current_user_identity.startswith('{'):
            try:
                current_user_dict = json.loads(current_user_identity)
                email = current_user_dict.get("email")
                role = current_user_dict.get("role")
                userId = current_user_dict.get("userId")
            except:
                print("Failed to parse JSON identity")
                return jsonify({"error": "Invalid user identity"}), 400
        elif isinstance(current_user_identity, dict):
            email = current_user_identity.get("email")
            role = current_user_identity.get("role")
            userId = current_user_identity.get("userId")
        else:
            return jsonify({"error": "Invalid user identity"}), 400
        
        # Verify user is a recruiter
        if role != "recruiter":
            return jsonify({"error": "Only recruiters can post jobs"}), 403
        
        # Get job data from request
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No job data provided"}), 400
        
        # Validate required fields
        required_fields = ["title", "company", "location", "description"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Find user by email
        user = mongo.db.users.find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Create job document
        job = {
            "title": data["title"],
            "company": data["company"],
            "location": data["location"],
            "description": data["description"],
            "skills": data.get("skills", []),
            "recruiterId": str(user["_id"]),
            "recruiterEmail": email,
            "active": True,
            "applications": [],
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow()
        }
        
        # Insert job into MongoDB
        result = mongo.db.jobs.insert_one(job)
        
        # Return job with ID
        job["_id"] = str(result.inserted_id)
        
        print(f"Job created successfully: {job['title']}")
        
        return jsonify({
            "success": True,
            "message": "Job posted successfully",
            "job": job
        }), 201
    
    except Exception as e:
        print(f"Error creating job: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to create job: {str(e)}"}), 500

# Get all jobs for the applicant view
@app.route("/api/jobs", methods=["GET"])
@jwt_required()
def get_jobs():
    try:
        # Get query parameters for filtering
        active_only = request.args.get('active', 'true').lower() == 'true'
        
        # Build query
        query = {}
        if active_only:
            query["active"] = True
        
        # Get jobs from MongoDB
        jobs = list(mongo.db.jobs.find(query).sort("created_at", -1))
        
        # Convert ObjectIds to strings for JSON serialization and rename fields
        for job in jobs:
            job["_id"] = str(job["_id"])
            # Convert created_at to createdAt for frontend compatibility
            if "created_at" in job:
                job["createdAt"] = job.pop("created_at").isoformat()
            if "updated_at" in job:
                job["updatedAt"] = job.pop("updated_at").isoformat()
        
        return jsonify({"jobs": jobs}), 200
    
    except Exception as e:
        print(f"Error getting jobs: {str(e)}")
        return jsonify({"error": f"Failed to get jobs: {str(e)}"}), 500

# Get jobs posted by the current recruiter
@app.route("/api/recruiter/jobs", methods=["GET"])
@jwt_required()
def get_recruiter_jobs():
    try:
        # Get current user identity
        current_user_identity = get_jwt_identity()
        
        # Parse user identity
        if isinstance(current_user_identity, str) and current_user_identity.startswith('{'):
            try:
                current_user_dict = json.loads(current_user_identity)
                email = current_user_dict.get("email")
                role = current_user_dict.get("role")
            except:
                print("Failed to parse JSON identity")
                return jsonify({"error": "Invalid user identity"}), 400
        elif isinstance(current_user_identity, dict):
            email = current_user_identity.get("email")
            role = current_user_identity.get("role")
        else:
            return jsonify({"error": "Invalid user identity"}), 400
        
        # Verify user is a recruiter
        if role != "recruiter":
            return jsonify({"error": "Only recruiters can access their posted jobs"}), 403
        
        # Find user by email
        user = mongo.db.users.find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get jobs from MongoDB where recruiterId matches
        jobs = list(mongo.db.jobs.find({"recruiterId": str(user["_id"])}).sort("created_at", -1))
        
        # Convert ObjectIds to strings for JSON serialization and rename fields
        for job in jobs:
            job["_id"] = str(job["_id"])
            # Convert created_at to createdAt for frontend compatibility
            if "created_at" in job:
                job["createdAt"] = job.pop("created_at").isoformat()
            if "updated_at" in job:
                job["updatedAt"] = job.pop("updated_at").isoformat()
        
        return jsonify({"jobs": jobs}), 200
    
    except Exception as e:
        print(f"Error getting recruiter jobs: {str(e)}")
        return jsonify({"error": f"Failed to get recruiter jobs: {str(e)}"}), 500

# Get a specific job by ID
@app.route("/api/jobs/<job_id>", methods=["GET"])
@jwt_required()
def get_job(job_id):
    try:
        # Get current user identity
        current_user_identity = get_jwt_identity()
        
        # Check if this is a request from the management page
        is_management = request.args.get('management', 'false').lower() == 'true'
        
        # Parse user identity if we need to check ownership
        if is_management:
            if isinstance(current_user_identity, str) and current_user_identity.startswith('{'):
                try:
                    current_user_dict = json.loads(current_user_identity)
                    email = current_user_dict.get("email")
                    role = current_user_dict.get("role")
                except:
                    print("Failed to parse JSON identity")
                    return jsonify({"error": "Invalid user identity"}), 400
            elif isinstance(current_user_identity, dict):
                email = current_user_identity.get("email")
                role = current_user_identity.get("role")
            else:
                return jsonify({"error": "Invalid user identity"}), 400
                
            # Verify user is a recruiter if management access is requested
            if role != "recruiter":
                return jsonify({"error": "Only recruiters can manage jobs"}), 403
        
        # Get job from MongoDB
        job = mongo.db.jobs.find_one({"_id": ObjectId(job_id)})
        
        if not job:
            return jsonify({"error": "Job not found"}), 404
            
        # If this is a management request, check if the job belongs to this recruiter
        if is_management:
            user = mongo.db.users.find_one({"email": email})
            if not user or str(user["_id"]) != job.get("recruiterId"):
                return jsonify({"error": "You do not have permission to manage this job"}), 403
        
        # Convert ObjectId to string for JSON serialization
        job["_id"] = str(job["_id"])
        
        # Convert created_at to createdAt for frontend compatibility
        if "created_at" in job:
            job["createdAt"] = job.pop("created_at").isoformat()
        if "updated_at" in job:
            job["updatedAt"] = job.pop("updated_at").isoformat()
        
        return jsonify({"job": job}), 200
    
    except Exception as e:
        print(f"Error getting job: {str(e)}")
        return jsonify({"error": f"Failed to get job: {str(e)}"}), 500

# Apply for a job
@app.route("/api/jobs/<job_id>/apply", methods=["POST"])
@jwt_required()
def apply_for_job(job_id):
    try:
        # Get current user identity
        current_user_identity = get_jwt_identity()
        
        # Parse user identity
        if isinstance(current_user_identity, str) and current_user_identity.startswith('{'):
            try:
                current_user_dict = json.loads(current_user_identity)
                email = current_user_dict.get("email")
                role = current_user_dict.get("role")
            except:
                print("Failed to parse JSON identity")
                return jsonify({"error": "Invalid user identity"}), 400
        elif isinstance(current_user_identity, dict):
            email = current_user_identity.get("email")
            role = current_user_identity.get("role")
        else:
            return jsonify({"error": "Invalid user identity"}), 400
        
        # Verify user is an applicant
        if role != "applicant":
            return jsonify({"error": "Only applicants can apply for jobs"}), 403
        
        # Find user by email
        user = mongo.db.users.find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Check if job exists
        job = mongo.db.jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            return jsonify({"error": "Job not found"}), 404
        
        # Check if the job is active
        if not job.get("active", True):
            return jsonify({"error": "This job is no longer accepting applications"}), 400
        
        # Check if user has already applied
        existing_application = mongo.db.applications.find_one({
            "jobId": job_id,
            "applicantId": str(user["_id"])
        })
        
        if existing_application:
            return jsonify({"error": "You have already applied for this job"}), 400
        
        # Get application data from request
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No application data provided"}), 400
        
        # Validate resume data
        if not data.get("resumeData"):
            return jsonify({"error": "Resume is required"}), 400
        
        # Create application document
        application = {
            "jobId": job_id,
            "jobTitle": job.get("title"),
            "companyName": job.get("company"),
            "applicantId": str(user["_id"]),
            "applicantName": user.get("name", ""),
            "applicantEmail": email,
            "resumeData": data.get("resumeData"),
            "matchScore": data.get("matchScore", 0),
            "status": "pending",
            "notes": "",
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow()
        }
        
        # Insert application into MongoDB
        result = mongo.db.applications.insert_one(application)
        application_id = result.inserted_id
        
        # Add application reference to job
        mongo.db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$push": {"applications": str(application_id)}}
        )
        
        # Return application with ID
        application["_id"] = str(application_id)
        
        print(f"Application submitted successfully for job: {job['title']}")
        
        # Trigger AI analysis in the background
        try:
            import requests
            import threading
            
            def trigger_analysis():
                try:
                    # Allow some time for the application to be fully saved
                    import time
                    time.sleep(1)
                    
                    analysis_url = "http://localhost:5002/api/analyze-application"
                    analysis_payload = {
                        "application_id": str(application_id),
                        "job_id": job_id
                    }
                    
                    response = requests.post(analysis_url, json=analysis_payload)
                    
                    if response.status_code == 200:
                        print(f"AI analysis triggered successfully for application {application_id}")
                    else:
                        print(f"AI analysis request failed with status {response.status_code}: {response.text}")
                        
                except Exception as e:
                    print(f"Error triggering AI analysis: {str(e)}")
            
            # Start analysis in background thread
            analysis_thread = threading.Thread(target=trigger_analysis)
            analysis_thread.daemon = True
            analysis_thread.start()
            
            print("Started background analysis of application")
            
        except Exception as e:
            print(f"Failed to trigger AI analysis: {str(e)}")
            # Continue with the application process even if analysis fails
        
        return jsonify({
            "success": True,
            "message": "Application submitted successfully",
            "application": {
                "id": application["_id"],
                "jobTitle": application["jobTitle"],
                "companyName": application["companyName"],
                "status": application["status"],
                "appliedAt": application["created_at"].isoformat()
            }
        }), 201
    
    except Exception as e:
        print(f"Error applying for job: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to apply for job: {str(e)}"}), 500

# Get applicants for a job (recruiter only)
@app.route("/api/jobs/<job_id>/applicants", methods=["GET"])
@jwt_required()
def get_job_applicants(job_id):
    try:
        # Get current user identity
        current_user_identity = get_jwt_identity()
        
        # Parse user identity
        if isinstance(current_user_identity, str) and current_user_identity.startswith('{'):
            try:
                current_user_dict = json.loads(current_user_identity)
                email = current_user_dict.get("email")
                role = current_user_dict.get("role")
            except:
                print("Failed to parse JSON identity")
                return jsonify({"error": "Invalid user identity"}), 400
        elif isinstance(current_user_identity, dict):
            email = current_user_identity.get("email")
            role = current_user_identity.get("role")
        else:
            return jsonify({"error": "Invalid user identity"}), 400
        
        # Verify user is a recruiter
        if role != "recruiter":
            return jsonify({"error": "Only recruiters can access job applicants"}), 403
        
        # Find user by email
        user = mongo.db.users.find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Check if job exists and belongs to this recruiter
        job = mongo.db.jobs.find_one({
            "_id": ObjectId(job_id),
            "recruiterId": str(user["_id"])
        })
        
        if not job:
            return jsonify({"error": "Job not found or you don't have permission to access it"}), 404
        
        # Get all applications for this job
        applications = list(mongo.db.applications.find({"jobId": job_id}))
        
        # Process applications for the response
        processed_applications = []
        for app in applications:
            # Convert ObjectIds to strings and rename _id to id for frontend compatibility
            app_id = str(app["_id"])
            del app["_id"]
            app["id"] = app_id
            
            # Format dates
            if "created_at" in app:
                app["appliedAt"] = app.pop("created_at").isoformat()
            if "updated_at" in app:
                app["updatedAt"] = app.pop("updated_at").isoformat()
            
            # Remove resume data for the list view (will be fetched individually)
            if "resumeData" in app:
                del app["resumeData"]
            
            processed_applications.append(app)
        
        return jsonify({
            "success": True,
            "applications": processed_applications
        }), 200
    
    except Exception as e:
        print(f"Error getting job applicants: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to get job applicants: {str(e)}"}), 500

# Update application status (recruiter only)
@app.route("/api/applications/<application_id>/status", methods=["PUT"])
@jwt_required()
def update_application_status(application_id):
    try:
        # Get current user identity
        current_user_identity = get_jwt_identity()
        
        # Parse user identity
        if isinstance(current_user_identity, str) and current_user_identity.startswith('{'):
            try:
                current_user_dict = json.loads(current_user_identity)
                email = current_user_dict.get("email")
                role = current_user_dict.get("role")
            except:
                print("Failed to parse JSON identity")
                return jsonify({"error": "Invalid user identity"}), 400
        elif isinstance(current_user_identity, dict):
            email = current_user_identity.get("email")
            role = current_user_identity.get("role")
        else:
            return jsonify({"error": "Invalid user identity"}), 400
        
        # Verify user is a recruiter
        if role != "recruiter":
            return jsonify({"error": "Only recruiters can update application status"}), 403
        
        # Find user by email
        user = mongo.db.users.find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get data from request
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        if "status" not in data:
            return jsonify({"error": "Status is required"}), 400
        
        # Get optional notes from the recruiter
        recruiter_notes = data.get("notes", "")
        
        # Validate status
        new_status = data["status"]
        valid_statuses = ["pending", "reviewed", "shortlisted", "rejected"]
        if new_status not in valid_statuses:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400
        
        # Get the application
        application = mongo.db.applications.find_one({"_id": ObjectId(application_id)})
        if not application:
            return jsonify({"error": "Application not found"}), 404
        
        # Check if the job belongs to this recruiter
        job = mongo.db.jobs.find_one({
            "_id": ObjectId(application["jobId"]),
            "recruiterId": str(user["_id"])
        })
        
        if not job:
            return jsonify({"error": "You don't have permission to update this application"}), 403
        
        # Update the application status
        result = mongo.db.applications.update_one(
            {"_id": ObjectId(application_id)},
            {
                "$set": {
                    "status": new_status,
                    "notes": recruiter_notes,
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({"error": "Failed to update application status"}), 500
            
        # If this is a final decision (shortlisted or rejected), generate feedback via AI
        feedback = ""
        if new_status in ["shortlisted", "rejected"]:
            try:
                import requests
                
                # Call the AI service to generate feedback
                ai_url = "http://localhost:5002/api/update-application-status"
                ai_payload = {
                    "application_id": str(application_id),
                    "status": new_status,
                    "notes": recruiter_notes
                }
                
                print(f"Sending AI feedback request for application {application_id} with status {new_status}")
                response = requests.post(ai_url, json=ai_payload)
                
                if response.status_code == 200:
                    ai_response = response.json()
                    feedback = ai_response.get("feedback", "")
                    print(f"AI feedback generated for {new_status} application")
                else:
                    print(f"AI feedback request failed with status {response.status_code}: {response.text}")
                    
            except Exception as e:
                print(f"Error generating AI feedback: {str(e)}")
                import traceback
                traceback.print_exc()
                # Continue with the status update even if feedback generation fails
            
            # Create a notification for the applicant
            try:
                # Convert shortlisted to accepted for notification status
                notification_status = "accepted" if new_status == "shortlisted" else new_status
                
                print(f"Creating notification for applicant {application['applicantId']} about {new_status} status")
                
                # Ensure notifications collection exists
                if "notifications" not in mongo.db.list_collection_names():
                    print("Creating notifications collection")
                    mongo.db.create_collection("notifications")
                
                # Make sure we have the applicant user ID
                applicant_id = application.get("applicantId")
                if not applicant_id:
                    print(f"No applicantId found in application {application_id}, trying to find applicant by email")
                    # Try to find the applicant by email if ID is missing
                    applicant_email = application.get("applicantEmail")
                    if applicant_email:
                        applicant = mongo.db.users.find_one({"email": applicant_email})
                        if applicant:
                            applicant_id = str(applicant["_id"])
                
                if not applicant_id:
                    print(f"Could not determine applicant ID for application {application_id}")
                    return jsonify({"error": "Could not determine applicant ID"}), 500
                
                notification = {
                    "userId": applicant_id,
                    "type": "status",
                    "jobId": str(application["jobId"]),
                    "jobTitle": application.get("jobTitle", job.get("title", "Job")),
                    "company": application.get("companyName", job.get("company", "Company")),
                    "status": notification_status,
                    "read": False,
                    "timestamp": datetime.datetime.utcnow()
                }
                
                print(f"Notification to be created: {notification}")
                
                # Insert notification into MongoDB
                mongo.db.notifications.insert_one(notification)
                print(f"Created notification for applicant {applicant_id} about {new_status} status")
            except Exception as e:
                print(f"Error creating notification: {str(e)}")
                import traceback
                traceback.print_exc()
                # Continue even if notification creation fails
        
        return jsonify({
            "success": True,
            "message": f"Application status updated to {new_status}",
            "feedback": feedback
        }), 200
    
    except Exception as e:
        print(f"Error updating application status: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to update application status: {str(e)}"}), 500

# Test endpoint to create a notification for current user
@app.route("/api/test/create-notification", methods=["POST"])
@jwt_required()
def test_create_notification():
    try:
        # Get current user identity
        current_user_identity = get_jwt_identity()
        
        # Parse user identity
        if isinstance(current_user_identity, str) and current_user_identity.startswith('{'):
            try:
                current_user_dict = json.loads(current_user_identity)
                email = current_user_dict.get("email")
                role = current_user_dict.get("role")
            except Exception as e:
                print(f"Failed to parse JSON identity: {str(e)}")
                return jsonify({"error": "Invalid user identity"}), 400
        elif isinstance(current_user_identity, dict):
            email = current_user_identity.get("email")
            role = current_user_identity.get("role")
        else:
            return jsonify({"error": "Invalid user identity"}), 400
        
        # Find user by email
        user = mongo.db.users.find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = str(user["_id"])
        
        # Get data from request or use defaults
        data = request.get_json() or {}
        
        # Create test notification
        notification = {
            "userId": user_id,
            "type": data.get("type", "status"),
            "jobId": data.get("jobId", "test-job-id"),
            "jobTitle": data.get("jobTitle", "Test Job"),
            "company": data.get("company", "Test Company"),
            "status": data.get("status", "accepted"),
            "read": False,
            "timestamp": datetime.datetime.utcnow()
        }
        
        # Ensure notifications collection exists
        if "notifications" not in mongo.db.list_collection_names():
            mongo.db.create_collection("notifications")
            mongo.db.notifications.create_index("timestamp")
            mongo.db.notifications.create_index("userId")
        
        # Insert notification
        result = mongo.db.notifications.insert_one(notification)
        
        return jsonify({
            "success": True,
            "message": "Test notification created",
            "notification_id": str(result.inserted_id)
        }), 201
        
    except Exception as e:
        print(f"Error creating test notification: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to create test notification: {str(e)}"}), 500

# Get notifications for current user
@app.route("/api/notifications", methods=["GET"])
@jwt_required()
def get_notifications():
    try:
        print("Notifications API endpoint called")
        
        # Get current user identity
        current_user_identity = get_jwt_identity()
        print(f"User identity: {current_user_identity}")
        
        # Parse user identity
        if isinstance(current_user_identity, str) and current_user_identity.startswith('{'):
            try:
                current_user_dict = json.loads(current_user_identity)
                email = current_user_dict.get("email")
                role = current_user_dict.get("role")
            except Exception as e:
                print(f"Failed to parse JSON identity: {str(e)}")
                return jsonify({"error": "Invalid user identity"}), 400
        elif isinstance(current_user_identity, dict):
            email = current_user_identity.get("email")
            role = current_user_identity.get("role")
        else:
            print(f"Invalid user identity type: {type(current_user_identity)}")
            return jsonify({"error": "Invalid user identity"}), 400
        
        print(f"Looking up user with email: {email}, role: {role}")
        
        # Find user by email
        user = mongo.db.users.find_one({"email": email})
        if not user:
            print(f"User not found with email: {email}")
            return jsonify({"error": "User not found"}), 404
        
        user_id = str(user["_id"])
        print(f"Found user with ID: {user_id}")
        
        # Get all notifications for this user
        print(f"Fetching notifications for user ID: {user_id}")
        query = {"userId": user_id}
        print(f"Query: {query}")
        
        # Check if notifications collection exists
        if "notifications" not in mongo.db.list_collection_names():
            print("Notifications collection does not exist - creating it")
            mongo.db.create_collection("notifications")
        
        notifications = list(mongo.db.notifications.find(query).sort("timestamp", -1))
        print(f"Found {len(notifications)} notifications")
        
        # Format notifications for response
        formatted_notifications = []
        for notification in notifications:
            print(f"Processing notification: {notification}")
            
            # Convert ObjectId to string
            notification["id"] = str(notification["_id"])
            del notification["_id"]
            
            # Format timestamp
            if "timestamp" in notification:
                try:
                    # Simple timestamp formatting
                    timestamp = notification["timestamp"]
                    notification["timestamp"] = timestamp.isoformat()
                    
                    # Generate a human-readable timestamp
                    now = datetime.datetime.utcnow()
                    diff = now - timestamp
                    
                    days = diff.days
                    seconds = diff.seconds
                    hours = seconds // 3600
                    minutes = (seconds % 3600) // 60
                    
                    if days > 0:
                        notification["timestamp_readable"] = f"{days} days ago"
                    elif hours > 0:
                        notification["timestamp_readable"] = f"{hours} hours ago"
                    elif minutes > 0:
                        notification["timestamp_readable"] = f"{minutes} minutes ago"
                    else:
                        notification["timestamp_readable"] = "just now"
                except Exception as e:
                    print(f"Error formatting timestamp: {str(e)}")
                    notification["timestamp_readable"] = "recently"
            
            formatted_notifications.append(notification)
        
        response_data = {"notifications": formatted_notifications}
        print(f"Returning response: {response_data}")
        return jsonify(response_data), 200
    
    except Exception as e:
        print(f"Error getting notifications: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to get notifications: {str(e)}"}), 500

# Get applicant's application status and feedback
@app.route("/api/applications/status", methods=["GET"])
@jwt_required()
def get_application_status():
    try:
        # Get current user identity
        current_user_identity = get_jwt_identity()
        
        # Parse user identity
        if isinstance(current_user_identity, str) and current_user_identity.startswith('{'):
            try:
                current_user_dict = json.loads(current_user_identity)
                email = current_user_dict.get("email")
                role = current_user_dict.get("role")
            except:
                print("Failed to parse JSON identity")
                return jsonify({"error": "Invalid user identity"}), 400
        elif isinstance(current_user_identity, dict):
            email = current_user_identity.get("email")
            role = current_user_identity.get("role")
        else:
            return jsonify({"error": "Invalid user identity"}), 400
        
        # Verify user is an applicant
        if role != "applicant":
            return jsonify({"error": "This endpoint is for applicants only"}), 403
        
        # Find user by email
        user = mongo.db.users.find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get application ID from query param if provided
        application_id = request.args.get('application_id')
        
        if application_id:
            # Get specific application
            application = mongo.db.applications.find_one({
                "_id": ObjectId(application_id),
                "applicantId": str(user["_id"])
            })
            
            if not application:
                return jsonify({"error": "Application not found or you don't have access"}), 404
            
            # Get feedback for this application
            try:
                import requests
                
                # Call the AI service to get feedback
                ai_url = f"http://localhost:5002/api/get-application-feedback?application_id={application_id}"
                
                response = requests.get(ai_url)
                
                if response.status_code == 200:
                    ai_response = response.json()
                    application_data = ai_response.get("application", {})
                    
                    # Format the response
                    formatted_response = {
                        "application": {
                            "id": str(application["_id"]),
                            "jobTitle": application.get("jobTitle", ""),
                            "companyName": application.get("companyName", ""),
                            "status": application.get("status", "pending"),
                            "appliedAt": application.get("created_at").isoformat() if application.get("created_at") else "",
                            "updatedAt": application.get("updated_at").isoformat() if application.get("updated_at") else "",
                            "matchScore": application.get("matchScore", 0)
                        }
                    }
                    
                    # Add feedback if available
                    if "feedback" in application_data:
                        formatted_response["application"]["feedback"] = application_data["feedback"]
                    
                    # Add improvement areas if rejected
                    if application.get("status") == "rejected" and "improvement_areas" in application_data:
                        formatted_response["application"]["improvementAreas"] = application_data["improvement_areas"]
                        formatted_response["application"]["missingSkills"] = application_data["missing_skills"]
                    
                    # Add strengths if shortlisted
                    if application.get("status") == "shortlisted" and "strengths" in application_data:
                        formatted_response["application"]["strengths"] = application_data["strengths"]
                    
                    return jsonify(formatted_response), 200
                else:
                    # Fallback to basic info if AI service fails
                    return jsonify({
                        "application": {
                            "id": str(application["_id"]),
                            "jobTitle": application.get("jobTitle", ""),
                            "companyName": application.get("companyName", ""),
                            "status": application.get("status", "pending"),
                            "appliedAt": application.get("created_at").isoformat() if application.get("created_at") else "",
                            "updatedAt": application.get("updated_at").isoformat() if application.get("updated_at") else "",
                            "matchScore": application.get("matchScore", 0)
                        }
                    }), 200
                    
            except Exception as e:
                print(f"Error getting AI feedback: {str(e)}")
                # Return basic application info without AI feedback
                return jsonify({
                    "application": {
                        "id": str(application["_id"]),
                        "jobTitle": application.get("jobTitle", ""),
                        "companyName": application.get("companyName", ""),
                        "status": application.get("status", "pending"),
                        "appliedAt": application.get("created_at").isoformat() if application.get("created_at") else "",
                        "updatedAt": application.get("updated_at").isoformat() if application.get("updated_at") else "",
                        "matchScore": application.get("matchScore", 0)
                    }
                }), 200
        else:
            # Get all applications for this user
            applications = list(mongo.db.applications.find({"applicantId": str(user["_id"])}))
            
            # Format response
            formatted_applications = []
            for app in applications:
                formatted_app = {
                    "id": str(app["_id"]),
                    "jobTitle": app.get("jobTitle", ""),
                    "companyName": app.get("companyName", ""),
                    "status": app.get("status", "pending"),
                    "appliedAt": app.get("created_at").isoformat() if app.get("created_at") else "",
                    "updatedAt": app.get("updated_at").isoformat() if app.get("updated_at") else "",
                    "matchScore": app.get("matchScore", 0)
                }
                formatted_applications.append(formatted_app)
            
            return jsonify({"applications": formatted_applications}), 200
    
    except Exception as e:
        print(f"Error getting application status: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to get application status: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001) 