from app.ingestion.parsers import CashArCsvParser
from datetime import datetime
from decimal import Decimal

# Helper to normalize VCH ID
def normalize_vch(v):
    if v.lower() in ['nan', 'none', 'null', '']: return ""
    return v

def test_match_logic():
    # Simulate a MATCH pair
    # Cash: P5438,2024-06-05,VCH_MATCH_238,Sales Charges Apply,13318.78
    # AR:   P5438,2024-06-05,VCH_MATCH_238,Receive,13318.78

    cash_row = b"Portfolio_ID,Val_Date,Vch_ID,Transaction_Name,DB_amount\nP5438,2024-06-05,VCH_MATCH_238,Sales Charges Apply,13318.78"
    ar_row = b"Portfolio_ID,Val_Date,Vch_ID,Transaction_Name,Credit_Amount\nP5438,2024-06-05,VCH_MATCH_238,Receive,13318.78"

    print("Parsing Cash...")
    parser_c = CashArCsvParser(source="CASH")
    entries_c = parser_c.parse(cash_row)
    c = entries_c[0]
    print(f"Cash Entry: {c}")

    print("Parsing AR...")
    parser_r = CashArCsvParser(source="AR")
    entries_r = parser_r.parse(ar_row)
    r = entries_r[0]
    print(f"AR Entry: {r}")

    # Generate Keys
    # Based on car_core.py logic
    # key = (portfolio_id, value_date, vch_id, abs(amount))
    
    # Simulate extraction from DB models which might strip more or less
    c_pid = c['portfolio_id'].strip() if c['portfolio_id'] else ""
    c_date = c['value_date']
    c_vch = c['reference_no'].strip() if c['reference_no'] else "" # parsers.py maps vch_id to reference_no
    # Wait, parsers.py maps vch_id to vch_id? No, let's check parsers.py again.
    # Lines 286: raw_vch = ...
    # BUT entries.append({ ..., "reference_no": ref, ...}) where ref is vch_id?
    # No, look at `col_map`.
    # `parsers.py` line 232 uses `reference_no: ref` where ref comes from `raw_ref` which comes from `col_map['ref']`... 
    # BUT `CashArCsvParser` uses different logic!
    # Let's check `CashArCsvParser` `entries.append` logic (I missed reading it).
    
    # If the parser maps vch_id to something else, that's critical. `BrokerCsvParser` uses `reference_no`.
    # `CashArCsvParser` probably uses `vch_id` key in dict? 
    # I need to see the `entries.append` part of `CashArCsvParser`.

    # Assuming standardized keys for now based on previous `BrokerCsvParser`.
    # Let's inspect `entries` keys from parser output first.

    print(f"Cash Keys: {c.keys()}")

if __name__ == "__main__":
    test_match_logic()
