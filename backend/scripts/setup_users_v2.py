import sys
import os
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Add the backend directory to the sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import Recon_Users, Recon_Role_mst
from app.core.security import get_password_hash
from app.core.config import settings

def setup_users():
    print(f"Connecting to DB: Host={settings.DB_HOST}, Port={settings.DB_PORT}, Name={settings.DB_NAME}, User={settings.DB_USER}")
    db = SessionLocal()
    try:
        # 1. DELETE existing users with specific roles (Admin, Investment Manager)
        # We find the role IDs first to be safe, or just delete based on current knowledge
        # The user asked to "delete existing admin and investment manager user"
        # We will delete users associated with these roles or strict email match if roles are ambiguous
        # Best approach: Find roles by name, then delete users who have those roles.
        
        roles_to_reset = ["Admin", "Investment Manager", "Analyst"]
        
        print("Cleaning up existing users and roles...")
        for role_name in roles_to_reset:
            role = db.query(Recon_Role_mst).filter(Recon_Role_mst.Role_Name == role_name).first()
            if role:
                # Delete users with this role
                users = db.query(Recon_Users).filter(Recon_Users.Role_id == role.id).all()
                for user in users:
                    db.delete(user)
                    print(f"Deleted user: {user.Email_id}")
                
                
        # Commit deletions
        db.commit()

        # 2. Ensure Roles Exist
        # We explicitly want to remove Investment Manager if it exists as a role object, 
        # but we already deleted users for it. Now we can try to delete the role itself if it's not needed.
        # The user said "remove investment manager role and add anylist role"
        
        inv_role = db.query(Recon_Role_mst).filter(Recon_Role_mst.Role_Name == "Investment Manager").first()
        if inv_role:
            db.delete(inv_role)
            print("Deleted Role: Investment Manager")
            db.commit()

        required_roles = ["Admin", "Analyst"]
        role_map = {}
        
        for role_name in required_roles:
            role = db.query(Recon_Role_mst).filter(Recon_Role_mst.Role_Name == role_name).first()
            if not role:
                role = Recon_Role_mst(Role_Name=role_name, CreatedBy="Script")
                db.add(role)
                db.commit()
                db.refresh(role)
                print(f"Created role: {role_name}")
            role_map[role_name] = role.id

        # 3. Create New Users
        # Admin: admin01@nimb / admin@0001
        admin_email = "admin01@nimb"
        admin_pass = "admin@0001"
        
        if not db.query(Recon_Users).filter(Recon_Users.Email_id == admin_email).first():
            new_admin = Recon_Users(
                User_Name="Admin User",
                Email_id=admin_email,
                Password=get_password_hash(admin_pass),
                Role_id=role_map["Admin"],
                CreatedBy="Script"
            )
            db.add(new_admin)
            print(f"Created user: {admin_email}")

        # Analyst: ashu009@nimb / ashu@2004
        analyst_email = "ashu009@nimb"
        analyst_pass = "ashu@2004"
        
        if not db.query(Recon_Users).filter(Recon_Users.Email_id == analyst_email).first():
            new_analyst = Recon_Users(
                User_Name="Ashu Analyst",
                Email_id=analyst_email,
                Password=get_password_hash(analyst_pass),
                Role_id=role_map["Analyst"],
                CreatedBy="Script"
            )
            db.add(new_analyst)
            print(f"Created user: {analyst_email}")

        db.commit()
        print("User setup completed successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    setup_users()
