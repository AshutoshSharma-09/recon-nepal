from app.ingestion.parsers import CashArCsvParser
from datetime import date
from decimal import Decimal

def test_match_logic():
    # Simulate a MATCH pair
    # Cash: P5438,2024-06-05,VCH_MATCH_238,Sales Charges Apply,13318.78
    # AR:   P5438,2024-06-05,VCH_MATCH_238,Receive,13318.78

    cash_content = b"Portfolio_ID,Val_Date,Vch_ID,Transaction_Name,DB_amount\nP5438,2024-06-05,VCH_MATCH_238,Sales Charges Apply,13318.78"
    ar_content = b"Portfolio_ID,Val_Date,Vch_ID,Transaction_Name,Credit_Amount\nP5438,2024-06-05,VCH_MATCH_238,Receive,13318.78"

    print("Parsing Cash...")
    parser_c = CashArCsvParser(source="CASH")
    entries_c = parser_c.parse(cash_content)
    c = entries_c[0]
    
    print(f"Parsing AR...")
    parser_r = CashArCsvParser(source="AR")
    entries_r = parser_r.parse(ar_content)
    r = entries_r[0]

    print(f"Cash Validation Error: {c.get('validation_error')}")
    print(f"AR Validation Error: {r.get('validation_error')}")

    # Inspect Types
    print(f"Cash Amount Type: {type(c['amount'])} Value: {c['amount']}")
    print(f"AR Amount Type: {type(r['amount'])} Value: {r['amount']}")
    print(f"Cash Date Type: {type(c['value_date'])} Value: {c['value_date']}")

    # Simulate Key Generation (from car_core.py)
    # key = (portfolio_id, value_date, vch_id, abs(amount))
    
    def get_key(entry):
        pid = entry['portfolio_id'].strip() if entry['portfolio_id'] else ""
        vch = entry['vch_id'].strip() if entry['vch_id'] else ""
        d = entry['value_date']
        # Simulate DB Decimal -> float conversion
        # In DB model it is Numeric(18,2). Parser returns Decimal.
        # So float(Decimal) matches logic.
        amt = abs(float(entry['amount']))
        return (pid, d, vch, amt)

    k_c = get_key(c)
    k_r = get_key(r)

    print(f"Cash Key: {k_c}")
    print(f"AR Key:   {k_r}")

    if k_c == k_r:
        print("KEYS MATCH!")
        
        # Test Transaction Name Logic
        c_txn = (c['transaction_name'] or "").strip().lower()
        r_txn = (r['transaction_name'] or "").strip().lower()
        
        print(f"Cash Txn: '{c_txn}'")
        print(f"AR Txn:   '{r_txn}'")
        
        if c_txn == "sales charges apply":
            if r_txn == "receive":
                print("TRANSACTION NAMES MATCH RULES! (Success)")
            else:
                print(f"TRANSACTION NAME MISMATCH: Needed 'receive', got '{r_txn}'")
        else:
            print("Standard Match (Success)")
            
    else:
        print("KEYS DO NOT MATCH!")
        if k_c[0] != k_r[0]: print(f"Portfolio Mismatch: {k_c[0]} != {k_r[0]}")
        if k_c[1] != k_r[1]: print(f"Date Mismatch: {k_c[1]} != {k_r[1]}")
        if k_c[2] != k_r[2]: print(f"Vch Mismatch: {k_c[2]} != {k_r[2]}")
        if k_c[3] != k_r[3]: print(f"Amount Mismatch: {k_c[3]} != {k_r[3]}")

if __name__ == "__main__":
    test_match_logic()
