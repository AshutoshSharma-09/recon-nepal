import sys
import os

# Set up file logging
log_file = "d:/PMS_RECON/NIMB-RECON/backend/reset_debug.log"
with open(log_file, "w") as f:
    sys.stdout = f
    sys.stderr = f
    print("Starting debug script...")
    print(f"CWD: {os.getcwd()}")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
    
    try:
        print("Attempting imports...")
        from app.database import engine
        from app.models import Base
        from sqlalchemy import text
        print("Imports successful.")
        
        # Explicitly drop old tables and types to handle rename migration
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS audit_logs CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS \"BB_recon_findings\" CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS \"BB_recon_matches_trail\" CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS \"BB_recon_matches\" CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS \"BB_recon_batches\" CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS \"BB_staging_broker_entries\" CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS \"BB_staging_bank_entries\" CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS \"BB_Recon_Files\" CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS \"Recon_Device_Info\" CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS \"Recon_login_logout\" CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS \"Recon_Users\" CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS \"Recon_Role_mst\" CASCADE"))

            # Drop Data from Previous Schema (Old Names)
            conn.execute(text("DROP TABLE IF EXISTS recon_findings CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS recon_matches CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS recon_batches CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS staging_broker_entries CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS staging_bank_entries CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS recon_files CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
            # conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE")) 

            # Drop Enums (Cascade should handle it but good to be sure if orphaned)
            conn.execute(text("DROP TYPE IF EXISTS batchstatus CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS matchkind CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS filesource CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS findingtype CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS sourceenum CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS findingside CASCADE"))
            
            conn.commit()
            print("Old tables and types dropped (Raw SQL).")

        print("Dropping tables (Metadata)...")
        Base.metadata.drop_all(bind=engine)
        print("Tables dropped (Metadata).")
        
        print("Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("Tables created.")
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
