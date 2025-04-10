from pymongo import MongoClient
import bcrypt
import os
import datetime

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['jobmatchdb']

# Check if users collection already has data
if db.users.count_documents({}) > 0:
    print("Database already has users. Skipping initialization.")
    exit(0)

# Create sample users
sample_users = [
    {
        "email": "recruiter@example.com",
        "password": bcrypt.hashpw("password123".encode('utf-8'), bcrypt.gensalt()),
        "role": "recruiter",
        "name": "Sample Recruiter",
        "created_at": datetime.datetime.utcnow()
    },
    {
        "email": "applicant@example.com",
        "password": bcrypt.hashpw("password123".encode('utf-8'), bcrypt.gensalt()),
        "role": "applicant",
        "name": "Sample Applicant",
        "created_at": datetime.datetime.utcnow()
    }
]

# Insert sample users
result = db.users.insert_many(sample_users)
print(f"Created {len(result.inserted_ids)} sample users")

# Ensure the notifications collection exists
if 'notifications' not in db.list_collection_names():
    # Create the notifications collection with a timestamp index
    db.create_collection('notifications')
    db.notifications.create_index('timestamp')
    db.notifications.create_index('userId')
    print("Created notifications collection with indexes")

print("\nSample login credentials:")
print("Recruiter: recruiter@example.com / password123")
print("Applicant: applicant@example.com / password123")
print("\nYou can now log in with these credentials at http://localhost:3000/login") 