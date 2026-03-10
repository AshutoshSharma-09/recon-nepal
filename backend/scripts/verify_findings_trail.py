import asyncio
import sys
import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date
from unittest.mock import MagicMock

# Setup Paths and Envs
sys.path.append(os.path.join(os.getcwd(), 'backend'))
# Clean existing test DB
if os.path.exists("./test.db"):
    os.remove("./test.db")

os.environ["DB_USER"] = "test"
os.environ["DB_PASSWORD"] = "test"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_NAME"] = "test"
os.environ["DB_PORT"] = "5432"
os.environ["API_KEYS"] = '{"test-key": "admin"}'
os.environ["UPLOAD_DIR"] = "."

# Setup Test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# INJECT TEST ENGINE into app.database check
import app.database
app.database.engine = test_engine
app.database.SessionLocal = TestingSessionLocal

# MOCK create_all to prevent real DB connection in app.main
import app.database
import app.models as app_models # Alias to avoid shadowing
# The Base instance is shared. Base.metadata is shared.
original_create_all = app_models.Base.metadata.create_all
app_models.Base.metadata.create_all = MagicMock()

from app.main import app
from app.database import Base, get_db
from app.core.security import get_api_key, Actor
from app.models import (
    BB_Recon_Files, BB_recon_batches, BB_staging_bank_entries, BB_staging_broker_entries,
    BB_recon_matches, BB_recon_findings, BB_recon_matches_trail, BB_recon_findings_trail,
    SourceEnum, BatchStatus, MatchKind, FindingType, FindingSide
)

# Restore and create tables
app_models.Base.metadata.create_all = original_create_all
Base.metadata.create_all(bind=test_engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

def override_get_api_key():
    return Actor(user_id=1, name="Test User", role="admin")

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_api_key] = override_get_api_key

# Setup Client
transport = ASGITransport(app=app)

async def run_verification():
    print("Starting Verification...")
    
    # DEBUG: Check tables
    inspector = inspect(test_engine)
    tables = inspector.get_table_names()
    print(f"DEBUG: Existing Tables in DB: {tables}")

    db = TestingSessionLocal()
    
    # 1. Setup Data
    print("Setting up data...")
    file_bank = BB_Recon_Files(source=SourceEnum.BANK, file_name="bank.txt", file_checksum="1", mime_type="text/plain")
    file_broker = BB_Recon_Files(source=SourceEnum.BROKER, file_name="broker.csv", file_checksum="2", mime_type="text/csv")
    db.add(file_bank)
    db.add(file_broker)
    db.flush()
    
    batch = BB_recon_batches(
        broker_file_id=file_broker.id,
        bank_file_id=file_bank.id,
        status=BatchStatus.RUNNING
    )
    db.add(batch)
    db.flush()
    
    # Create Entries
    be1 = BB_staging_broker_entries(
        id=1, # Explicit ID for SQLite
        file_id=file_broker.id, value_date=date(2025, 1, 1), 
        amount_signed=100.0, reference_no="REF1", portfolio_id="P1", type_raw="Test"
    )
    ke1 = BB_staging_bank_entries(
        id=1, # Explicit ID for SQLite
        file_id=file_bank.id, value_date=date(2025, 1, 1), 
        amount_signed=100.0, reference_no="REF1", portfolio_id="P1", type_raw="Test"
    )
    db.add(be1)
    db.add(ke1)
    db.flush()
    
    # Create Initial Findings (as if they were unmatched)
    f_br = BB_recon_findings(
        batch_id=batch.id, side=FindingSide.BROKER, entry_id=be1.id, portfolio_id="P1",
        finding_type=FindingType.UNMATCHED, finding_reason="Initial",
        created_at=datetime.utcnow(), created_by="system"
    )
    f_bk = BB_recon_findings(
        batch_id=batch.id, side=FindingSide.BANK, entry_id=ke1.id, portfolio_id="P1",
        finding_type=FindingType.UNMATCHED, finding_reason="Initial",
        created_at=datetime.utcnow(), created_by="system"
    )
    db.add(f_br)
    db.add(f_bk)
    db.flush()
    
    # Also create trails 
    t_br = BB_recon_findings_trail(
        BB_recon_finding_ID=f_br.id, batch_id=batch.id, side=FindingSide.BROKER, entry_id=be1.id,
        finding_type=FindingType.UNMATCHED, Action="CREATED"
    )
    t_bk = BB_recon_findings_trail(
        BB_recon_finding_ID=f_bk.id, batch_id=batch.id, side=FindingSide.BANK, entry_id=ke1.id,
        finding_type=FindingType.UNMATCHED, Action="CREATED"
    )
    db.add(t_br)
    db.add(t_bk)
    db.commit()
    
    print(f"Initial Findings Created: IDs {f_br.id}, {f_bk.id}")

    # Use AsyncClient for requests
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 2. Manual Match
        print("\nExecuting Manual Match...")
        payload = {
            "batch_id": batch.id,
            "bank_entry_ids": [ke1.id],
            "broker_entry_ids": [be1.id],
            "note": "Manual Match Test"
        }
        
        # CORRECTED PATH
        resp = await client.post("/api/v1/recon/manual-match", json=payload)
        if resp.status_code != 200:
            print(f"Manual Match Failed: {resp.text}")
            return

        print("Manual Match Success.")
        
        # Verify Findings Soft Deleted (Trail Added)
        db.expire_all()
        
        f_br_check = db.query(BB_recon_findings).filter(BB_recon_findings.id == f_br.id).first()
        trails_br = db.query(BB_recon_findings_trail).filter(BB_recon_findings_trail.BB_recon_finding_ID == f_br.id).order_by(BB_recon_findings_trail.id.desc()).all()
        
        print(f"Finding BR ID: {f_br_check.id}")
        print(f"Trails Count: {len(trails_br)}")
        if len(trails_br) > 0:
            print(f"Latest Trail Action: {trails_br[0].Action}")
            if trails_br[0].Action == "MATCHED_MANUAL":
                print("SUCCESS: Finding BR marked as MATCHED_MANUAL via trail.")
            else:
                print("FAILURE: Latest trail is not MATCHED_MANUAL.")
        else:
            print("FAILURE: No trail created.")
        
        # Verify Matches Check
        match = db.query(BB_recon_matches).filter(BB_recon_matches.batch_id == batch.id).first()
        if match:
             print(f"Match Created: {match.match_id}")
        else:
             print("FAILURE: Match not created.")
             return
        
        # 3. Break Match
        print("\nExecuting Break Match...")
        payload_break = {
            "batch_id": batch.id,
            "match_id": match.match_id
        }
        # CORRECTED PATH
        resp = await client.post("/api/v1/recon/break-match", json=payload_break)
        if resp.status_code != 200:
            print(f"Break Match Failed: {resp.text}")
            return
            
        print("Break Match Success.")
        
        # Verify Findings Revived
        db.expire_all()
        f_br_check = db.query(BB_recon_findings).filter(BB_recon_findings.id == f_br.id).first()
        trails_br = db.query(BB_recon_findings_trail).filter(BB_recon_findings_trail.BB_recon_finding_ID == f_br.id).order_by(BB_recon_findings_trail.id.desc()).all()
        
        print(f"Latest Trail Action after Break: {trails_br[0].Action}")
        if trails_br[0].Action == "UNMATCHED_BREAK":
            print("SUCCESS: Finding BR revived as UNMATCHED_BREAK.")
        else:
            print("FAILURE: Latest trail is not UNMATCHED_BREAK.")
            
        # 4. Check Recon Response (API)
        print("\nChecking Recon Response (should show findings)...")
        # CORRECTED PATH
        resp = await client.get(f"/api/v1/recon/latest") # Should pick up our batch
        data = resp.json()
        
        found = False
        if 'broker_records' in data:
            for r in data['broker_records']:
                if r['id'] == str(be1.id):
                    print(f"Broker Record Found. Status: {r['match_status']}")
                    if r['match_status'] in ["UNMATCHED", "EXCEPTION"]:
                        found = True
                    else:
                        print(f"FAILURE: Status is {r['match_status']}, expected UNMATCHED")
        else:
            print(f"No broker_records in response: {data}")
        
        if found:
            print("SUCCESS: Record visible in API response.")
        else:
            print("FAILURE: Record not found in API response.")

    db.close()

if __name__ == "__main__":
    asyncio.run(run_verification())
