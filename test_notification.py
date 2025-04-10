import requests
import json
import sys

# Configuration
API_URL = "http://localhost:5001/api"  # Update this to match your API server

def create_test_notification(token):
    """Create a test notification for the authenticated user"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # Notification data
    data = {
        "type": "status",
        "jobTitle": "Frontend Developer",
        "company": "Tech Innovations",
        "status": "accepted"  # or "rejected"
    }
    
    response = requests.post(
        f"{API_URL}/test/create-notification",
        headers=headers,
        json=data
    )
    
    print(f"Response status code: {response.status_code}")
    print(f"Response body: {json.dumps(response.json(), indent=2)}")
    
    return response.status_code == 201

def fetch_notifications(token):
    """Fetch notifications for the authenticated user"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(
        f"{API_URL}/notifications",
        headers=headers
    )
    
    print(f"Fetch notifications status code: {response.status_code}")
    print(f"Notifications response: {json.dumps(response.json(), indent=2)}")
    
    return response.status_code == 200

def main():
    # Check if token was provided
    if len(sys.argv) < 2:
        print("Usage: python test_notification.py <auth_token>")
        print("Get your auth token from the browser's localStorage after logging in")
        return
    
    token = sys.argv[1]
    
    # Create a notification
    print("Creating test notification...")
    if create_test_notification(token):
        print("Notification created successfully!")
    else:
        print("Failed to create notification")
        return
    
    # Fetch notifications to verify
    print("\nFetching notifications...")
    if fetch_notifications(token):
        print("Notifications fetched successfully!")
    else:
        print("Failed to fetch notifications")

if __name__ == "__main__":
    main() 