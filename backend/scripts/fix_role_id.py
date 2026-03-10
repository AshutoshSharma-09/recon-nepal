import sys
print("Script started...")
import os
from dotenv import load_dotenv
from sqlalchemy import text

# Logging setup
log_file = os.path.join(os.path.dirname(__file__), '..', 'fix_role.log')
sys.stdout = open(log_file, 'w')
sys.stderr = sys.stdout

# Load .env file explicitly
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Add the backend directory to the sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal
from app.models import Recon_Users, Recon_Role_mst

def fix_role_id():
    db = SessionLocal()
    try:
        print("Checking Roles...")
        analyst_role = db.query(Recon_Role_mst).filter(Recon_Role_mst.Role_Name == "Analyst").first()
        
        if not analyst_role:
            print("Analyst role not found.")
            return

        print(f"Current Analyst Role ID: {analyst_role.id}")
        
        if analyst_role.id == 2:
            print("Analyst Role ID is already 2. No action needed.")
            return

        # Check if ID 2 is occupied
        role_at_2 = db.query(Recon_Role_mst).filter(Recon_Role_mst.id == 2).first()
        if role_at_2:
            print(f"Error: ID 2 is already occupied by role '{role_at_2.Role_Name}'.")
            # If it's some other role, we might need to delete it if it's garbage, but let's be safe.
            # Assuming user wants Analyst to be 2, and previously Invest Manager was 2 (and is deleted).
            return

        print("Migrating Analyst Role to ID 2...")
        
        # 1. Rename current Analyst role temporarily to free up the unique name constraint
        analyst_role.Role_Name = "Analyst_Old"
        db.commit()
        print("Renamed current Analyst role to 'Analyst_Old'")

        # 2. Create new Analyst Role with ID 2
        # We need to force ID 2. SQLAlchemy supports this if we explicit pass id.
        new_role = Recon_Role_mst(
            id=2, 
            Role_Name="Analyst", 
            Is_Active=True, 
            CreatedBy="FixScript"
        )
        db.add(new_role)
        db.commit()
        print("Created new Analyst role with ID 2")

        # 3. Migrate Users
        users = db.query(Recon_Users).filter(Recon_Users.Role_id == analyst_role.id).all()
        for user in users:
            user.Role_id = 2
            print(f"Updated user {user.Email_id} to Role ID 2")
        
        db.commit()

        # 4. Delete Old Role
        db.delete(analyst_role)
        db.commit()
        print("Deleted old Analyst role")

        # 5. Fix Sequence (Postgres specific, but useful if we want next to be 3)
        # We assume Postgres given the earlier output format
        try:
            # This resets the sequence to the MAX(id)
            db.execute(text("SELECT setval(pg_get_serial_sequence('\"Recon_Role_mst\"', 'ID'), coalesce(max(\"ID\"), 1)) FROM \"Recon_Role_mst\";"))
            db.commit()
            print("Updated ID sequence")
        except Exception as seq_err:
            print(f"Could not update sequence (might not be Postgres or permission issue): {seq_err}")

        print("SUCCESS: Analyst role ID updated to 2.")

    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_role_id()
