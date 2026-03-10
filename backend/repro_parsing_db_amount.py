from app.ingestion.parsers import CashArCsvParser
from decimal import Decimal

def test_parser_db_amount():
    # Simulate CSV content with DB_amount header
    csv_content = b"Portfolio_ID,Val_Date,Vch_ID,Transaction_Name,DB_amount\nP1987,2024-02-05,VCH_CASH_UN_15,Stock Purchase,2555.01"
    
    parser = CashArCsvParser(source="CASH")
    entries = parser.parse(csv_content)
    
    print(f"Parsed {len(entries)} entries.")
    for e in entries:
        amt = e['amount']
        # Also check raw data to confirm DB_amount was preserved
        raw_amt = e.get('raw_data', {}).get('DB_amount')
        print(f"Amount: '{amt}'")
        print(f"Raw Entry Keys: {e.keys()}")
        if amt is None:
            print("FAIL: Amount parsed as None (likely missing mapping for DB_amount)")
        else:
            print(f"SUCCESS: Amount parsed as {amt}")

if __name__ == "__main__":
    test_parser_db_amount()
