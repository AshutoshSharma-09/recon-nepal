import sys
import os
from dotenv import load_dotenv
from sqlalchemy import text

# Logging setup
log_file = "d:/PMS_RECON/NIMB-RECON/backend/reset_full.log"
sys.stdout = open(log_file, 'w')
sys.stderr = sys.stdout

# Load .env file explicitly
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Add the backend directory to the sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import engine, SessionLocal
from app.models import Base, Recon_Users, Recon_Role_mst
from app.core.security import get_password_hash

def reset_db_full():
    print("Starting Full Database Reset...")
    
    # 1. Drop All Tables
    try:
        with engine.connect() as conn:
            # Drop tables in dependency order (reverse of creation usually, or just cascade)
            # using cascade with raw SQL is safest for thorough cleanup
            tables_to_drop = [
                "audit_logs",
                "\"BB_recon_findings\"", "\"BB_recon_matches_trail\"", "\"BB_recon_matches\"", 
                "\"BB_recon_batches\"", "\"BB_staging_broker_entries\"", "\"BB_staging_bank_entries\"",
                "\"BB_Recon_Files\"", "\"Recon_Device_Info\"", "\"Recon_login_logout\"", 
                "\"Recon_Users\"", "\"Recon_Role_mst\""
            ]
            
            for table in tables_to_drop:
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            
            # Also drop Enums to be clean
            enums_to_drop = [
                "batchstatus", "matchkind", "filesource", "findingtype", 
                "sourceenum", "findingside"
            ]
            for enum_name in enums_to_drop:
                conn.execute(text(f"DROP TYPE IF EXISTS {enum_name} CASCADE"))
                
            conn.commit()
            print("Dropped all existing tables and types.")
    except Exception as e:
        print(f"Error dropping tables: {e}")
        # Continue anyway, Base.metadata.drop_all might catch the rest

    # 2. Re-create Schema
    print("Re-creating schema...")
    Base.metadata.create_all(bind=engine)
    print("Schema created.")

    # 3. Seed Data
    db = SessionLocal()
    try:
        print("Seeding default data...")
        
        # Create Roles with Valid IDs
        # Admin -> 1
        admin_role = Recon_Role_mst(id=1, Role_Name="Admin", CreatedBy="SYSTEM")
        db.add(admin_role)
        
        # Analyst -> 2
        analyst_role = Recon_Role_mst(id=2, Role_Name="Analyst", CreatedBy="SYSTEM")
        db.add(analyst_role)
        
        db.commit()
        print("Roles seeded: Admin(1), Analyst(2)")

        # Create Users
        # Admin User
        admin_user = Recon_Users(
            User_Name="System Admin",
            Email_id="admin01@nimb",
            Password=get_password_hash("admin@0001"),
            Role_id=1,
            Is_Active=True,
            CreatedBy="SYSTEM"
        )
        db.add(admin_user)

        # Analyst User
        analyst_user = Recon_Users(
            User_Name="Ashutosh Sharma",
            Email_id="ashu009@nimb",
            Password=get_password_hash("ashu@2004"),
            Role_id=2, # Explicitly linked to Analyst
            Is_Active=True,
            CreatedBy="SYSTEM"
        )
        db.add(analyst_user)

        db.commit()
        print("Users seeded: admin01@nimb, ashu009@nimb")
        
        # Fix Sequence for Role ID (Postgres)
        try:
             db.execute(text("SELECT setval(pg_get_serial_sequence('\"Recon_Role_mst\"', 'ID'), (SELECT MAX(\"ID\") FROM \"Recon_Role_mst\"))"))
             db.commit()
             print("Sequence updated.")
        except Exception as e:
            print(f"Sequence update skipped/failed (ignore if not Postgres): {e}")

        print("FULL RESET SUCCESSFUL")

    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_db_full()
