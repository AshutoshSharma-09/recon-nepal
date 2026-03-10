import sys
import os
from dotenv import load_dotenv
from sqlalchemy import text

# Load .env file explicitly
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Add the backend directory to the sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal, engine
from app.core.config import settings

def fix_schema():
    print(f"Connecting to DB: Host={settings.DB_HOST}, Port={settings.DB_PORT}, Name={settings.DB_NAME}, User={settings.DB_USER}")
    
    # We need to verify if we are connecting to localhost (from outside docker) or db (from inside)
    # Since we run this from host, ensure env points to localhost if mapped
    # But settings.DB_HOST might be 'db' now because I changed docker-compose to force it?
    # No, docker-compose env override is for the container.
    # The .env file on disk (which this script loads) still says: DB_HOST=localhost
    # So this script will work from the host.
    
    db = SessionLocal()
    try:
        print("Dropping table 'Recon_Device_Info'...")
        # Use raw SQL to drop table
        db.execute(text('DROP TABLE IF EXISTS "Recon_Device_Info" CASCADE;'))
        db.commit()
        print("Table dropped successfully.")
        
        print("IMPORTANT: restart your backend server to recreate the table with correct schema.")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_schema()
