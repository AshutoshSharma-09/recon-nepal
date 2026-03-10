import os
import sys

# Ensure we can import app code
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'backend'))

from sqlalchemy import create_engine, text

# Connection Config
DATABASE_URL = "postgresql://pms_user:password@localhost:5432/pms_db"

def reset_db():
    print(f"Connecting to: {DATABASE_URL}")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            print("WARNING: This will DELETE ALL DATA from reconciliation tables.")
            
            # List of tables to truncate
            # Order matters less with CASCADE, but good to be explicit
            tables = [
                "recon_matches",
                "recon_findings",
                "recon_batches",
                "staging_bank_entries", 
                "staging_broker_entries",
                "recon_files",
                "audit_logs"
            ]
            
            print(f"Truncating tables: {', '.join(tables)}")
            
            # Using CASCADE to handle foreign keys automatically
            conn.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE;"))
            conn.commit()
            
            print("Database cleared successfully!")

    except Exception as e:
        print(f"Operation Failed: {e}")

if __name__ == "__main__":
    confirm = input("Are you sure you want to delete all data? (y/n): ")
    if confirm.lower() == 'y':
        reset_db()
    else:
        print("Operation cancelled.")
