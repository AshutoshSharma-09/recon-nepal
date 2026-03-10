import sys
import os
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal
from app.models import Recon_login_logout

def dump_logs():
    db = SessionLocal()
    try:
        records = db.query(Recon_login_logout).order_by(desc(Recon_login_logout.id)).limit(5).all()
        
        with open("backend/db_dump.txt", "w") as f:
            for r in records:
                f.write(f"ID: {r.id}\n")
                f.write(f"Email: {r.Email_id}\n")
                f.write(f"Login Time: {r.login_timestamp}\n")
                f.write(f"Logout Time: {r.logout_timestamp}\n")
                f.write(f"Last Login Time: {r.Last_login_timestamp}\n")
                f.write("-" * 20 + "\n")
                
        print("Dump complete.")
    except Exception as e:
        print(f"Error dumping logs: {e}")
        with open("backend/db_dump.txt", "w") as f:
             f.write(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    dump_logs()
