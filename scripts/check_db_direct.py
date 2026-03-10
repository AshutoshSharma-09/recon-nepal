
import sys
import os

# Add backend to path - Assuming script is in c:\Desktop\PMS-RECON\scripts
# Backend is in c:\Desktop\PMS-RECON\backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(current_dir, '..', 'backend'))
sys.path.append(backend_path)

from app.database import SessionLocal
from app.models import StagingBankEntry, StagingBrokerEntry, ReconMatch, ReconFile, ReconBatch

def check_db():
    db = SessionLocal()
    try:
        print("--- Checking ReconFiles ---")
        files = db.query(ReconFile).all()
        for f in files:
            print(f"FileID: {f.id} | Name: {f.file_name} | Loaded: {f.loaded_at}")

        print("\n--- Checking ReconBatches ---")
        batches = db.query(ReconBatch).all()
        for b in batches:
            print(f"BatchID: {b.id} | BankFileID: {b.bank_file_id} | BrokerFileID: {b.broker_file_id} | Status: {b.status}")

        print("\n--- Checking StagingBankEntry ---")
        entries = db.query(StagingBankEntry).all()
        for e in entries:
            # Print specifically the ones we are interested in or all if small
            print(f"ID: {e.id} | Ref: {e.reference_no} | PID: {e.portfolio_id} | Amt: {e.amount_signed} | FileID: {e.file_id}")
            
        print("\n--- Checking ReconMatch ---")
        matches = db.query(ReconMatch).all()
        last_match_id = 0
        for m in matches:
             print(f"MatchID: {m.match_id} | BankID: {m.bank_entry_id} | BrokerID: {m.broker_entry_id}")
             last_match_id = m.id

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
