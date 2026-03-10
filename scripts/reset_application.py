import os
import sys
import shutil
import time

# Path fix to allow importing from backend
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'backend'))

# Mock Environment Variables if not set
os.environ.setdefault("DB_USER", "pms_user")
os.environ.setdefault("DB_PASSWORD", "password")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "pms_db")
os.environ.setdefault("API_KEYS", '["local-dev-key"]')
# IMPORTANT: Point to the correct uploads folder relative to project root
# Fix: Use absolute path derived from project_root to avoid CWD issues
os.environ.setdefault("UPLOAD_DIR", os.path.join(project_root, "backend", "uploads"))
os.environ.setdefault("MAX_UPLOAD_BYTES", "10485760")

from app.database import engine, Base
from app.models import * # Import all models

def clean_uploads():
    """Deletes all files in the uploads directory."""
    upload_dir = os.environ.get("UPLOAD_DIR")
    if not os.path.exists(upload_dir):
        print(f"Uploaded directory '{upload_dir}' does not exist. creating it...")
        os.makedirs(upload_dir, exist_ok=True)
        return

    print(f"Cleaning uploads directory: {upload_dir}")
    for filename in os.listdir(upload_dir):
        file_path = os.path.join(upload_dir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
            print(f"Deleted: {filename}")
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")
    
    # Recreate temp dir if needed by app
    os.makedirs(os.path.join(upload_dir, "temp"), exist_ok=True)

def recreate_db():
    """Drops and Recreates all tables."""
    print("Dropping all tables...")
    try:
        # Use raw SQL to force a complete reset of the public schema
        # This handles cases where old tables (not in current metadata) depend on types
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE;"))
            conn.execute(text("CREATE SCHEMA public;"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
            # conn.execute(text("GRANT ALL ON SCHEMA public TO pms_user;")) # strict permission if needed
            conn.commit()
        print("Schema reset complete.")
        
        print("Creating all tables...")
        Base.metadata.create_all(bind=engine)
        print("Tables created.")
    except Exception as e:
        print(f"Error acting on DB: {e}")
        print("Ensure the database container is running and credentials are correct.")
        sys.exit(1)

def main():
    print("⚠  WARNING: EXPERIMENTAL RESET SCRIPT")
    print("This will DELETE ALL DATA in the database and ALL UPLOADED FILES.")
    print("You have 5 seconds to Ctrl+C to cancel...")
    time.sleep(5)
    
    print("-" * 30)
    clean_uploads()
    print("-" * 30)
    recreate_db()
    print("-" * 30)
    print("✅ Application Reset Successfully! You can now start fresh.")

if __name__ == "__main__":
    main()
