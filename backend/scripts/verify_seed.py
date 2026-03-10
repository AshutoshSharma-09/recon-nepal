import sys
import os

# Set logs
log_file = "d:/PMS_RECON/NIMB-RECON/backend/verify_seed.log"
with open(log_file, "w") as f:
    sys.stdout = f
    sys.stderr = f
    
    # Add the backend directory to the sys.path
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

    try:
        from app.database import SessionLocal
        from app.models import Recon_Users, Recon_Role_mst
        from app.main import seed_users
        
        print("Running seed_users()...")
        seed_users()
        
        db = SessionLocal()
        try:
            print("Verifying Roles...")
            roles = db.query(Recon_Role_mst).all()
            for r in roles:
                print(f"Role: {r.Role_Name} (ID: {r.id})")
                
            print("Verifying Users...")
            users = db.query(Recon_Users).all()
            for u in users:
                print(f"User: {u.Email_id} (Role: {u.role.Role_Name}, ID: {u.role.id})")
                
            if len(users) >= 2 and len(roles) >= 2:
                print("VERIFICATION SUCCESSFUL")
            else:
                print("VERIFICATION FAILED: Missing users or roles")
                
        except Exception as e:
            print(f"Error querying DB: {e}")
        finally:
            db.close()
            
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
