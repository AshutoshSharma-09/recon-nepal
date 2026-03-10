import sys
import os
from decimal import Decimal, ROUND_HALF_UP

# Mock functions from parsers.py to reproduce exact logic
def parse_date(date_str):
    from datetime import datetime
    formats = ["%Y-%m-%d", "%d/%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except: continue
    return None

def parse_amount(amt_str, type_str):
    if not amt_str: return None
    clean_amt = str(amt_str).replace(',', '').replace('$', '').strip()
    try:
        val = Decimal(clean_amt)
    except: return None
    
    t = str(type_str).lower().strip()
    if t in ['debit', 'dr']: return -abs(val)
    if t in ['credit', 'cr']: return abs(val)
    return val

def test_line(line):
    print(f"Testing Line: '{line}'")
    parts = line.split()
    print(f"Parts: {parts}")
    
    if len(parts) < 4:
        print("Skipped (len < 4)")
        return

    raw_date = parts[0]
    raw_portfolio = parts[1]
    raw_type = parts[-1] 
    
    # Logic from CURRENT parsers.py
    candidate_amt = parts[-2]
    amount = parse_amount(candidate_amt, raw_type)
    
    if amount is not None:
        print("Amount Parsed Successfully")
        raw_ref = " ".join(parts[2:-2])
    else:
        print("Amount Parse Failed (Fallback)")
        amount = None
        raw_ref = " ".join(parts[2:-1])
        
    print(f"Date: {raw_date}")
    print(f"Portfolio: {raw_portfolio}")
    print(f"Ref: {raw_ref}")
    print(f"Amount: {amount}")

# Test with the problematic line constructed from screenshot
# "2025-11-22    NIBLJF134584    H-0-RCV551-90867    47,614.66    Credit"
# Maybe missing portfolio?
# "2025-11-22    H-0-RCV551-90867    47,614.66    Credit"
    
lines = [
    "2025-11-22    NIBLJF134584    H-0-RCV551-90867    47,614.66    Credit",
    "2025-02-04    NIBLQK742715    H-0-RCV846-75999         Debit",
    "2025-11-22    H-0-RCV551-90867    47,614.66    Credit" # Validating if portfolio was missing
]

for l in lines:
    test_line(l)
    print("-" * 20)
