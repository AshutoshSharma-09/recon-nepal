import sys
import os
import requests
import time
from datetime import datetime

# Add parent directory to path to import app modules if needed, 
# but here we will test via API mostly, or direct DB check.
# Actually, to check DB reliably without running the full app server in background, 
# we might want to use the app's database connection directly if we can't ensure the server is up.
# However, the user asked to "fix" it, implying the server might be running or valid to run.
# But 'run_command' doesn't easily let us start a server and keep it running while we run another script.
# So I will use direct DB manipulation to test the Logic if possible, 
# OR I can try to hit the running server if the user has one? 
# The user state says "Active Document: ...docker-compose.yml", maybe valid to assume I can run python scripts.

# Let's try to verify via direct DB checks and simulating the API logic if I can't hit a live URL.
# Wait, I changed `auth.py`. I want to verify the logic inside `auth.py`.
# I cannot easily invoke the FastAPI route handlers directly without a request context.
# So I will create a script that sets up a temporary TestClient (from fastapi.testclient) to test the flow.

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.models import Recon_Users, Recon_login_logout, Recon_Role_mst
from app.core import security

# Create an in-memory SQLite database for testing to avoid messing with real DB?
# Or use the real DB but with a test user?
# The user seems to be using postgres based on the screenshot (psql prompt).
# I should probably use the configured database but be careful.
# Actually, the user wants me to FIX it. 
# I will use TestClient with the current DB session overrides if possible, 
# or just rely on the existing DB connection.

client = TestClient(app)

def test_login_logout_flow():
    print("Starting Login/Logout Verification...")
    
    # 1. Login
    login_payload = {
        "email": "admin01@nimb",
        "password": "admin@0001" 
    }
    
    # Ensure user exists (admin01@nimb is seeded in main.py, so it should exist if app started once, 
    # but let's assume it does or we might fail).
    
    print(f"Attempting login with {login_payload['email']}...")
    response = client.post("/api/v1/auth/login", json=login_payload)
    
    if response.status_code != 200:
        print(f"Login failed: {response.status_code} - {response.text}")
        return
    
    data = response.json()
    token = data["access_token"]
    print("Login successful. Token received.")
    
    # Check DB for login record
    # We need to access the DB. We can use the app's engine.
    from app.database import SessionLocal
    db = SessionLocal()
    
    try:
        user = db.query(Recon_Users).filter(Recon_Users.Email_id == login_payload["email"]).first()
        if not user:
            print("User not found in DB! Strange.")
            return

        # Get latest login record
        latest_login = db.query(Recon_login_logout).filter(
            Recon_login_logout.Email_id == user.Email_id
        ).order_by(Recon_login_logout.login_timestamp.desc()).first()
        
        if not latest_login:
            print("No login record found!")
            return
            
        print(f"Login Record Found: ID={latest_login.id}, LoginTime={latest_login.login_timestamp}, LastLogin={latest_login.Last_login_timestamp}")
        
        login_time_1 = latest_login.login_timestamp
        
        # Wait a second to ensure timestamps differ
        time.sleep(1.5)
        
        # 2. Logout
        print("Attempting logout...")
        logout_headers = {"Authorization": f"Bearer {token}"}
        logout_response = client.post("/api/v1/auth/logout", headers=logout_headers)
        
        if logout_response.status_code != 200:
            print(f"Logout failed: {logout_response.status_code} - {logout_response.text}")
        else:
            print("Logout successful.")
            
        # Verify Logout Timestamp
        db.refresh(latest_login)
        print(f"Record after logout: ID={latest_login.id}, LogoutTime={latest_login.logout_timestamp}")
        
        if not latest_login.logout_timestamp:
            print("FAIL: Logout timestamp was not recorded!")
        else:
            print("PASS: Logout timestamp recorded.")

        # 3. Login Again to check Last_login_timestamp
        time.sleep(1.5)
        print("Attempting second login...")
        response_2 = client.post("/api/v1/auth/login", json=login_payload)
        
        if response_2.status_code == 200:
            print("Second login successful.")
            
            # Check new record
            new_login = db.query(Recon_login_logout).filter(
                Recon_login_logout.Email_id == user.Email_id
            ).order_by(Recon_login_logout.login_timestamp.desc()).first()
            
            print(f"New Login Record: ID={new_login.id}, LoginTime={new_login.login_timestamp}, LastLogin={new_login.Last_login_timestamp}")
            
            if new_login.id == latest_login.id:
                 print("FAIL: Did not create a new record?")
            else:
                 # Check if Last_login_timestamp matches the previous login's login_timestamp
                 # Note: SQLAlchemy returns datetime objects.
                 
                 # Precision issues might occur, let's compare as strings or with small delta?
                 # Actually, it should be exact if fetched from DB record.
                 
                 print(f"Expected LastLogin: {login_time_1}")
                 print(f"Actual LastLogin:   {new_login.Last_login_timestamp}")
                 
                 if new_login.Last_login_timestamp == login_time_1:
                     print("PASS: Last_login_timestamp matches previous login time.")
                 else:
                     print("FAIL: Last_login_timestamp mismatch!")
                     
    finally:
        db.close()

if __name__ == "__main__":
    test_login_logout_flow()
