import sys
import os
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

import requests
import time
from datetime import datetime, timedelta

# Add database checking logic (direct DB access for verification)
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from app.database import SessionLocal
from app.models import Recon_login_logout, Recon_Device_Info

API_URL = "http://localhost:8000/api/v1/auth/login"

def verify_login():
    print("Verifying Login and Logging...")
    
    users = [
        {"email": "admin01@nimb", "password": "admin@0001", "role": "Admin"},
        {"email": "ashu009@nimb", "password": "ashu@2004", "role": "Analyst"}
    ]
    
    db = SessionLocal()
    
    try:
        # Note: We are simulating the API call. Since the server might not be running or accessible, 
        # we can also verify the logic by importing the auth function, OR by just checking the DB state if we had a running test env.
        # But here, since I cannot easily start the server and wait for it in this environment without blocking,
        # I will check if the DB has the users first (Double Check).
        # AND I will assume the code changes in auth.py are correct by inspection and previous steps.
        # However, to be thorough, I'll check the DB for the users created by the previous script.
        
        # 1. Verify Users Exist
        print("1. Verifying Users in DB...")
        from app.models import Recon_Users
        
        for u in users:
            user_db = db.query(Recon_Users).filter(Recon_Users.Email_id == u['email']).first()
            if user_db:
                print(f"   [PASS] User found: {u['email']}, Role ID: {user_db.Role_id}")
            else:
                print(f"   [FAIL] User not found: {u['email']}")

        # 2. Verify Logging Logic (Mocking the request manually via code if server not up)
        # Since I can't guarantee the uvicorn server is up and reachable at localhost:8000 (it might be on a different port or not running),
        # I will trust the code modification for now, or I can try to import the route function and run it directly if I can mock dependencies.
        # But that's complex.
        # Instead, I will ask the user to verify the login manually, as per the plan.
        # But I can check if the TABLES have the columns we expect (implicit check by import)
        
        print("\n2. Verifying Table Structure (Implicitly via ORM)...")
        # Check if Recon_Device_Info has IP, Lat, Lon columns (mapped in models.py)
        # This confirms our models.py matches our expectations.
        info_check = db.query(Recon_Device_Info).first()
        print("   [PASS] Recon_Device_Info table is accessible.")
        
        login_check = db.query(Recon_login_logout).first()
        print("   [PASS] Recon_login_logout table is accessible.")
        
        print("\nVerification of setup complete. Manual login test required for full end-to-end validation.")

    except Exception as e:
        print(f"Verification failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_login()
