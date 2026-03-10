import sys
import os
import io
from datetime import date
from decimal import Decimal

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

from app.ingestion.parsers import BankTxtParser, BrokerCsvParser
from app.engine.core import ReconEngine
from app.database import SessionLocal, engine, Base
from app.models import ReconFile, FileSource, StagingBrokerEntry, StagingBankEntry, BatchStatus, MatchKind

def verify_portfolio_recon():
    print("running verification...")
    
    # 1. Setup DB Session
    db = SessionLocal()
    
    # 2. Mock Data
    bank_content = """Value Date Portfolio ID Reference No. Amount Type
2025-01-22 NIBLSY479164 H-O-RCV348-2213 118,478.96 Credit
2025-03-20 NIBLXD923944 ATM-WD-6416 464,685.78 Debit
""".encode('utf-8')

    broker_content = b"""Value Date, Portfolio ID, Reference No., Amount, Type
2025-01-22, NIBLSY479164, H-O-RCV348-2213, 118478.96, Credit
2025-03-20, NIBLXD923944, ATM-WD-6416, 464685.78, Debit
"""

    # 3. Test Parsers
    print("Testing Bank Parser...")
    bank_parser = BankTxtParser()
    bank_entries = bank_parser.parse(bank_content)
    assert len(bank_entries) == 2
    assert bank_entries[0]['portfolio_id'] == 'NIBLSY479164'
    print("✅ Bank Parser OK")

    print("Testing Broker Parser...")
    broker_parser = BrokerCsvParser()
    broker_entries = broker_parser.parse(broker_content)
    assert len(broker_entries) == 2
    assert broker_entries[0]['portfolio_id'] == 'NIBLSY479164'
    print("✅ Broker Parser OK")

    # 4. Insert Data into DB (Mocking Ingestion)
    # Create File Records
    bank_file = ReconFile(source=FileSource.BANK, file_name="test_bank.txt")
    broker_file = ReconFile(source=FileSource.BROKER, file_name="test_broker.csv")
    db.add(bank_file)
    db.add(broker_file)
    db.commit()
    db.refresh(bank_file)
    db.refresh(broker_file)

    # Insert Entries
    for e in bank_entries:
        db_entry = StagingBankEntry(
            file_id=bank_file.id,
            value_date=e['value_date'],
            portfolio_id=e['portfolio_id'],
            reference_no=e['reference_no'],
            amount_signed=e['amount_signed'],
            type_raw=e['type_raw']
        )
        db.add(db_entry)

    for e in broker_entries:
        db_entry = StagingBrokerEntry(
            file_id=broker_file.id,
            value_date=e['value_date'],
            portfolio_id=e['portfolio_id'],
            reference_no=e['reference_no'],
            amount_signed=e['amount_signed'],
            type_raw=e['type_raw']
        )
        db.add(db_entry)
    
    db.commit()

    # 5. Run Recon Engine
    print("Running Recon Engine...")
    engine_svc = ReconEngine(db)
    batch_id = engine_svc.run_batch(broker_file.id, bank_file.id, "TEST_USER")
    
    # 6. Verify Results
    print("Verifying Matches...")
    from app.models import ReconBatch, ReconMatch
    batch = db.query(ReconBatch).filter(ReconBatch.id == batch_id).first()
    assert batch.status == BatchStatus.COMPLETED
    
    matches = db.query(ReconMatch).filter(ReconMatch.batch_id == batch_id).all()
    print(f"Found {len(matches)} matches")
    assert len(matches) == 2
    
    print("✅ Verification Successful!")
    db.close()

if __name__ == "__main__":
    verify_portfolio_recon()
