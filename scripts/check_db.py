import sys
import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# Add backend to path to import app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'backend'))

try:
    from app.models import ReconMatch, ReconBatch, ReconFinding, StagingBankEntry, StagingBrokerEntry, AuditLog, ReconFile
    from app.database import SessionLocal, engine
except ImportError as e:
    print(f"Error importing app modules: {e}")
    print("Make sure you are running this from the project root (c:\\Desktop\\PMS-RECON)")
    sys.exit(1)

def print_separator(char='-', length=100):
    print(char * length)

def print_query(session, model, limit=50):
    table_name = model.__tablename__
    query = session.query(model)
    count = query.count()
    items = query.limit(limit).all()
    
    print(f"\nTABLE: {table_name} (Total: {count})")
    print_separator('=')
    
    if not items:
        print("  <EMPTY TABLE>")
        return

    # Get columns
    columns = [c.name for c in model.__table__.columns]
    
    # Calculate widths (simple)
    widths = {c: len(c) for c in columns}
    data = []
    for item in items:
        row = {}
        for c in columns:
            val = str(getattr(item, c))
            if len(val) > 50: val = val[:47] + "..."
            row[c] = val
            widths[c] = max(widths[c], len(val))
        data.append(row)
        
    # Print Header
    header = " | ".join(f"{c.ljust(widths[c])}" for c in columns)
    print(header)
    print_separator()
    
    # Print Rows
    for row in data:
        line = " | ".join(f"{row[c].ljust(widths[c])}" for c in columns)
        print(line)
        
    if count > limit:
        print(f"... and {count - limit} more records")

def main():
    print(f"Connecting to DB: {engine.url}")
    session = SessionLocal()

    try:
        # 1. Files
        print_query(session, ReconFile)
        
        # 2. Batches
        print_query(session, ReconBatch)
        
        # 3. Matches (Most important for user to see Manual/Auto)
        print_query(session, ReconMatch)
        
        # 4. Findings
        print_query(session, ReconFinding)
        
        # 5. Staging Entries (Sample)
        print_query(session, StagingBankEntry, limit=5)
        print_query(session, StagingBrokerEntry, limit=5)
        
        # 6. Audit Logs
        print_query(session, AuditLog)

    except Exception as e:
        print(f"Error inspecting DB: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    main()
