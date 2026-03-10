import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal
from app.models import Recon_Role_mst, Recon_Users

def verify():
    log_path = os.path.join(os.path.dirname(__file__), '..', 'id_check.log')
    with open(log_path, 'w') as f:
        try:
            db = SessionLocal()
            role = db.query(Recon_Role_mst).filter(Recon_Role_mst.Role_Name == 'Analyst').first()
            if role:
                f.write(f"Analyst Role ID: {role.id}\n")
                
                # Check users
                users = db.query(Recon_Users).filter(Recon_Users.Role_id == role.id).all()
                for u in users:
                    f.write(f"User: {u.Email_id} has Role ID: {u.Role_id}\n")
            else:
                f.write("Analyst role not found\n")
            db.close()
        except Exception as e:
            f.write(f"Error: {e}\n")

if __name__ == "__main__":
    verify()
