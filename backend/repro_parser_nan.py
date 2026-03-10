from app.ingestion.parsers import CashArCsvParser
from decimal import Decimal

def test_parser_nan():
    # Simulate CSV content with empty/nan amount
    # "nan" string typically parsed from pandas for missing entries
    csv_content = b"Value Date,Portfolio ID,Vch ID,Amount,Transaction Name\n2023-01-01,P123,V001,nan,Txn1\n2023-01-02,P124,V002,,Txn2\n2023-01-03,P125,V003,NaN,Txn3"
    
    parser = CashArCsvParser(source="CASH")
    entries = parser.parse(csv_content)
    
    print(f"Parsed {len(entries)} entries.")
    for e in entries:
        amt = e['amount']
        print(f"Amount: '{amt}' (Type: {type(amt)})")
        if amt is not None:
             try:
                 # Check if convertable to float without fail
                 f = float(amt)
                 import json
                 json.dumps({"amount": f})
                 print("JSON Dumps OK")
             except Exception as ex:
                 print(f"JSON Dumps FAILED: {ex}")

if __name__ == "__main__":
    test_parser_nan()
