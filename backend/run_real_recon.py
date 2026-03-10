from app.database import SessionLocal
from app.models import CR_Recon_Files, CR_SourceEnum
from app.engine.car_core import CarReconEngine
from sqlalchemy import desc

def run_recon():
    db = SessionLocal()
    try:
        print("Fetching latest files...")
        cash_file = db.query(CR_Recon_Files).filter(CR_Recon_Files.source == CR_SourceEnum.CASH).order_by(desc(CR_Recon_Files.loaded_at)).first()
        ar_file = db.query(CR_Recon_Files).filter(CR_Recon_Files.source == CR_SourceEnum.RECEIVABLE).order_by(desc(CR_Recon_Files.loaded_at)).first()
        
        if not cash_file or not ar_file:
            print("ERROR: Could not find both Cash and AR files.")
            return

        print(f"Using Cash File: ID={cash_file.id} Name={cash_file.file_name}")
        print(f"Using AR File:   ID={ar_file.id} Name={ar_file.file_name}")
        
        engine = CarReconEngine(db)
        print("Running Batch...")
        # Use a dummy actor name
        batch_id = engine.run_batch(cash_file.id, ar_file.id, "AutoMatchDebugScript")
        
        print(f"Batch {batch_id} Completed.")
        
        # Verify results
        from app.api.car_recon import _build_car_response
        res = _build_car_response(batch_id, db)
        summary = res.get("summary", {})
        print("\n--- Match Results ---")
        print(f"Total Matches:    {summary.get('total_matches')}")
        print(f"Auto Matches:     {summary.get('auto_match_count')}")
        print(f"Exceptions:       {summary.get('exception_count')}")
        print(f"Unmatched:        {summary.get('unmatched_count')}")
        
        # Check if AR entries are present in output
        ar_records = res.get("ar_records", [])
        
        with open("recon_results.txt", "w") as f:
            f.write("--- Match Results ---\n")
            f.write(f"Total Matches:    {summary.get('total_matches')}\n")
            f.write(f"Auto Matches:     {summary.get('auto_match_count')}\n")
            f.write(f"Exceptions:       {summary.get('exception_count')}\n")
            f.write(f"Unmatched:        {summary.get('unmatched_count')}\n")
            f.write(f"AR Records in Output: {len(ar_records)}\n")
            if len(ar_records) > 0:
                f.write(f"Sample AR Record: {ar_records[0]}\n")
            
    except Exception as e:
        with open("recon_results.txt", "w") as f:
            f.write(f"ERROR: {e}\n")
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    run_recon()
