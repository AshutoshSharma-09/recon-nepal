from app.database import engine, Base
from app.models import CR_recon_findings, CR_recon_findings_trail
from sqlalchemy import text

def fix_schema():
    conn = engine.connect()
    try:
        print("Dropping generic CR_recon_findings tables if they exist...")
        # We need to drop Trail first due to FK
        conn.execute(text("DROP TABLE IF EXISTS CR_recon_findings_trail"))
        conn.execute(text("DROP TABLE IF EXISTS CR_recon_findings"))
        conn.commit()
        
        print("Re-creating tables with updated Enum...")
        # This will create tables that are missing, i.e., the ones we just dropped
        Base.metadata.create_all(bind=engine)
        print("Schema fixed.")
    except Exception as e:
        print(f"Error fixing schema: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_schema()
