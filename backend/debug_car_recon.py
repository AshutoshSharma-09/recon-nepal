import pandas as pd
from app.ingestion.parsers import CashArCsvParser
from decimal import Decimal
import io

# Mock DB Models to simulate car_core logic
class MockEntry:
    def __init__(self, id, pid, date, vch, amt, txn, side):
        self.id = id
        self.portfolio_id = pid
        self.value_date = date
        self.vch_id = vch
        self.transaction_name = txn
        self.validation_error = None
        if side == "CASH":
            self.db_amount = amt
            self.cr_amount = None
        else:
            self.db_amount = None
            self.cr_amount = amt

def check_file_parsing(path, source):
    print(f"\n--- Parsing {source} ({path}) ---")
    try:
        with open(path, 'rb') as f:
            content = f.read()
        
        parser = CashArCsvParser(source=source)
        entries = parser.parse(content)
        print(f"Parsed {len(entries)} entries")
        if len(entries) > 0:
            print("Sample Entry 0:", entries[0])
        return entries
    except Exception as e:
        print(f"Parsing FAILED: {e}")
        return []

def simulate_matching(cash_entries, ar_entries):
    print("\n--- Simulating Matching Logic ---")
    
    # Convert to Mock Objects
    c_objs = [MockEntry(i, e['portfolio_id'], e['value_date'], e['vch_id'], e['amount'], e['transaction_name'], "CASH") for i, e in enumerate(cash_entries)]
    r_objs = [MockEntry(i, e['portfolio_id'], e['value_date'], e['vch_id'], e['amount'], e['transaction_name'], "AR") for i, e in enumerate(ar_entries)]

    # 1. Exception Check
    def is_exception(entry):
        # Critical Data Check
        if not entry.portfolio_id or str(entry.portfolio_id).strip() == "": return True
        if not entry.value_date: return True
        
        # User Rule: Exception if BOTH Vch ID and Amount are missing
        amt = entry.db_amount if hasattr(entry, 'db_amount') else entry.cr_amount
        has_amt = amt is not None
        vch = entry.vch_id
        has_vch = vch and str(vch).strip() not in ["", "nan", "NaN", "None"]
        
        if not has_vch and not has_amt:
            return True
        return False

    valid_c = [c for c in c_objs if not is_exception(c)]
    valid_r = [r for r in r_objs if not is_exception(r)]
    
    print(f"Exceptions: Cash={len(c_objs)-len(valid_c)}, AR={len(r_objs)-len(valid_r)}")
    print(f"Valid for Matching: Cash={len(valid_c)}, AR={len(valid_r)}")

    # 2. Build Lookup
    ar_lookup = {}
    for r in valid_r:
        if r.cr_amount is None: continue
        key = (
            str(r.portfolio_id).strip(),
            r.value_date,
            str(r.vch_id).strip(),
            abs(float(r.cr_amount))
        )
        if key not in ar_lookup: ar_lookup[key] = []
        ar_lookup[key].append(r)

    # 3. Match
    matches = 0
    for c in valid_c:
        if c.db_amount is None: continue
        key = (
            str(c.portfolio_id).strip(),
            c.value_date,
            str(c.vch_id).strip(),
            abs(float(c.db_amount))
        )
        
        if key in ar_lookup and ar_lookup[key]:
            c_txn = (c.transaction_name or "").strip().lower()
            match_found = False
            
            # Rule Match
            for r in ar_lookup[key]:
                r_txn = (r.transaction_name or "").strip().lower()
                if c_txn == "sales charges apply" and r_txn == "receive":
                    matches += 1
                    match_found = True
                    # In simulation we don't pop to check count easier
                    break
            
            # Fallback Exact Match
            if not match_found:
                 for r in ar_lookup[key]:
                    r_txn = (r.transaction_name or "").strip().lower()
                    if c_txn == r_txn:
                        matches += 1
                        match_found = True
                        break
            
            if match_found:
                print(f"MATCH FOUND! Key: {key}")
                if matches >= 5: break # Only show first 5

    print(f"\nTotal Matches Found (Simulation Limit): {matches}")

if __name__ == "__main__":
    c_entries = check_file_parsing("C:\\Desktop\\PMS-RECON\\Cash_ledger.csv", "CASH")
    r_entries = check_file_parsing("C:\\Desktop\\PMS-RECON\\Amount_Receivable.csv", "AR")
    
    if c_entries and r_entries:
        simulate_matching(c_entries, r_entries)
