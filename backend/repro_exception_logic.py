from datetime import date
from decimal import Decimal

# Mock Entry Class
class MockEntry:
    def __init__(self, pid, val_date, amount, vch_id, validation_error=None):
        self.portfolio_id = pid
        self.value_date = val_date
        self.db_amount = amount # Simulating Cash Entry
        self.vch_id = vch_id
        self.validation_error = validation_error

# Logic copied from car_core.py (to verify without DB dep)
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

def test_exception_logic():
    print("Testing Exception Logic...")
    
    # Case 1: All Good (Validation Error ignored)
    e1 = MockEntry("P1", date(2023,1,1), Decimal("100.00"), "V1", "Missing Something Else")
    if is_exception(e1):
        print("FAIL Case 1: Marked as Exception (Should be Valid)")
    else:
        print("PASS Case 1: Valid")

    # Case 2: Missing Amount AND Vch (Real Exception)
    e2 = MockEntry("P1", date(2023,1,1), None, "")
    if is_exception(e2):
        print("PASS Case 2: Exception (Correct)")
    else:
        print("FAIL Case 2: Marked Valid (Should be Exception)")

    # Case 3: Missing Vch but Has Amount (Valid)
    e3 = MockEntry("P1", date(2023,1,1), Decimal("50.00"), "")
    if is_exception(e3):
        print("FAIL Case 3: Marked as Exception (Should be Valid)")
    else:
        print("PASS Case 3: Valid")

    # Case 4: Missing Portfolio (Critical Exception)
    e4 = MockEntry("", date(2023,1,1), Decimal("100.00"), "V1")
    if is_exception(e4):
        print("PASS Case 4: Exception (Correct - Missing Portfolio)")
    else:
        print("FAIL Case 4: Valid (Should be Exception)")

if __name__ == "__main__":
    test_exception_logic()
