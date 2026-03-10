from app.database import SessionLocal, engine
from app.models import CR_recon_findings, FindingSide, FindingType, Base
from sqlalchemy import text

def test_enum_insert():
    db = SessionLocal()
    try:
        with open("debug_enum.log", "w") as f:
            f.write(f"FindingSide members: {list(FindingSide.__members__.keys())}\n")
            col_type = CR_recon_findings.side.type
            f.write(f"Column Enum values: {col_type.enums}\n")
        
        print(f"Repr(RECEIVABLE): {repr(FindingSide.RECEIVABLE)}")
        print("Attempting to insert Finding with 'CASH' (string)...")
        f = CR_recon_findings(
            batch_id=999999, 
            side="CASH",
            entry_id=1,
            finding_type=FindingType.UNMATCHED,
            finding_reason="Test"
        )
        db.add(f)
        db.commit()
        print("SUCCESS: Inserted (or at least passed constraint check)")
    except Exception as e:
        print(f"FAILED: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    test_enum_insert()
