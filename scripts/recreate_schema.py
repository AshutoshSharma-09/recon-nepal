import os
import sys

# Path fix
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'backend'))

# Mock Environment Variables if not set
os.environ.setdefault("DB_USER", "pms_user")
os.environ.setdefault("DB_PASSWORD", "password")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "pms_db")
os.environ.setdefault("API_KEYS", '["test-key"]')
os.environ.setdefault("UPLOAD_DIR", "./uploads")
os.environ.setdefault("MAX_UPLOAD_BYTES", "10485760")

from app.database import engine, Base
from app.models import * # Import all models to ensure they are registered

def recreate_db():
    print("⚠  WARNING: DROPPING ALL TABLES in 5 seconds. Ctrl+C to cancel.")
    import time
    time.sleep(5)
    
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    
    print("✅ Schema recreated successfully!")

if __name__ == "__main__":
    recreate_db()
