import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'backend'))

from app.models import StagingBankEntry
from app.database import SessionLocal

def inspect_ref():
    session = SessionLocal()
    # Search for the reference mentioned in the screenshot, or one that looks like it
    ref = "H-0-RCV551-90867" 
    print(f"Searching for Ref: {ref}")
    
    entries = session.query(StagingBankEntry).all() # Just get all and manually filter if needed, or filter by loose match
    
    found = False
    for e in entries:
        if ref in str(e.reference_no) or ref in str(e.portfolio_id):
            print(f"--- FOUND ENTRY ID {e.id} ---")
            print(f"Date: {e.value_date}")
            print(f"Portfolio: '{e.portfolio_id}'")
            print(f"Ref: '{e.reference_no}'")
            print(f"Amount: {e.amount_signed}")
            print(f"TypeRaw: '{e.type_raw}'")
            print(f"ValidationError: {e.validation_error}")
            print(f"RawData: '{e.raw_data}'")
            found = True
            
    if not found:
        print("No entry found matching that reference.")

if __name__ == "__main__":
    inspect_ref()
