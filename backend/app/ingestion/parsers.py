import pandas as pd
import re
from datetime import datetime
from typing import List, Dict, Optional
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import io

# Constants
MISSING_DATE = "MISSING_DATE"
MISSING_AMOUNT = "MISSING_AMOUNT"
MISSING_REF = "MISSING_REFERENCE"
MISSING_PORTFOLIO = "MISSING_PORTFOLIO_ID"

def parse_date(date_str: str) -> Optional[datetime.date]:
    """Tries to parse date from common formats to YYYY-MM-DD object"""
    if not date_str or not isinstance(date_str, str) or not date_str.strip():
        return None
    
    formats = [
        "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y",
        "%d-%b-%y", "%d-%b-%Y", # e.g. 12-Aug-23
        "%Y/%m/%d",
        "%m-%d-%Y",  # e.g. 12-21-2024
    ]
    
    clean_str = date_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(clean_str, fmt).date()
        except ValueError:
            continue
    return None

def parse_amount(amt_str: str, type_str: str) -> Optional[Decimal]:
    """
    Parses amount string to Decimal.
    Returns None if parsing fails (User Req: 'Parsing failures must return None, not 0.0').
    """
    if not amt_str: return None
    
    # Handle currency symbols if any (simple removal)
    clean_amt = str(amt_str).replace(',', '').replace('$', '').replace('Rs', '').strip()
    
    try:
        val = Decimal(clean_amt)
        # Round to 2 decimals
        val = val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (ValueError, InvalidOperation):
        return None
    
    # Sign logic
    t = str(type_str).lower().strip()
    if t in ['debit', 'dr', 'withdrawal']:
        res = -abs(val)
        return res
    elif t in ['credit', 'cr', 'deposit']:
        return abs(val)
    
    return val

class BankTxtParser:
    """
    Parses Bank Statement .TXT
    Format: Whitespace delimited
    Cols: Value Date | Reference No. | Amount | Type
    """
    def parse(self, file_content: bytes) -> List[Dict]:
        try:
            text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            # Fallback for legacy encodings
            text = file_content.decode('latin-1')
            
        lines = text.splitlines()
        entries = []
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Ignore divider lines (dashes, underscores)
            if set(line) <= {'-', '_', '=', ' '}:
                continue
            
            # Allow headers check (optional, skip if header)
            if "Value Date" in line and "Reference" in line:
                continue

            # Whitespace split
            parts = line.split()
            
            # User Change: Allow missing amount (len 4)
            if len(parts) < 4:
                # Requires Date, Portfolio, Ref(at least 1), Type (Amount might be missing)
                continue

            raw_type = parts[-1]
            candidate_amt = parts[-2]
            amount = parse_amount(candidate_amt, raw_type)
            
            # Adaptive logic: Check if first token is a Date
            raw_first = parts[0]
            val_date = parse_date(raw_first)
            
            if val_date:
                # Standard Alignment: Date(0) Port(1) ...
                raw_portfolio = parts[1]
                
                if amount is not None:
                    # Amount at -2
                    raw_ref = " ".join(parts[2:-2])
                else:
                    # Amount Missing, fallback
                    amount = None
                    raw_ref = " ".join(parts[2:-1])
            else:
                # Date Parse Failed. Assume DATE IS MISSING.
                # Shift Alignment: Port(0) ...
                val_date = None
                raw_portfolio = parts[0]
                
                if amount is not None:
                    # Amount at -2
                    raw_ref = " ".join(parts[1:-2])
                else:
                    # Amount Missing
                    amount = None
                    raw_ref = " ".join(parts[1:-1])

            # Normalization
            # val_date is already set
            # amount is already set
            ref = raw_ref.strip()
            portfolio_id = raw_portfolio.strip()
            
            # Track all missing fields
            missing_fields = []
            if not val_date:
                missing_fields.append("Date")
            if amount is None:
                missing_fields.append("Amount")
            if not portfolio_id:
                missing_fields.append("Portfolio ID")
            if not ref:
                missing_fields.append("Reference No.")
            
            # Generate validation error message
            validation_error = None
            if len(missing_fields) == 1:
                validation_error = f"Missing {missing_fields[0]}"
            elif len(missing_fields) > 1:
                validation_error = f"Missing Data ({', '.join(missing_fields)})"
            else:
                validation_error = None
                
            entries.append({
                "value_date": val_date,
                "portfolio_id": portfolio_id,
                "reference_no": ref,
                "amount_signed": amount if amount is not None else Decimal("0.00"),
                "type_raw": raw_type,
                "validation_error": validation_error,
                "raw_data": line
            })
            
        return entries

class BrokerCsvParser:
    """
    Parses Broker .CSV
    Header: Value Date, Portfolio ID, Reference No., Amount, Type
    """
    def parse(self, file_content: bytes) -> List[Dict]:
        # Read via pandas for strict CSV handling
        try:
            df = pd.read_csv(io.BytesIO(file_content))
        except Exception as e:
            return []
        
        # Normalize headers: strip quotes, spaces
        df.columns = [c.strip().replace('"', '').replace('.', '') for c in df.columns]
        
        entries = []
        
        # Expected Headers mapping
        col_map = {
            'date': next((c for c in df.columns if 'Date' in c), None),
            'portfolio': next((c for c in df.columns if 'Portfolio' in c), None),
            'ref': next((c for c in df.columns if 'Reference' in c or 'Ref' in c), None),
            'amt': next((c for c in df.columns if 'Amount' in c), None),
            'type': next((c for c in df.columns if 'Type' in c), None),
        }
        
        for _, row in df.iterrows():
            raw_date = str(row[col_map['date']]) if col_map['date'] else ""
            raw_portfolio = str(row[col_map['portfolio']]) if col_map['portfolio'] else ""
            raw_ref = str(row[col_map['ref']]) if col_map['ref'] else ""
            raw_amt = str(row[col_map['amt']]) if col_map['amt'] else ""
            raw_type = str(row[col_map['type']]) if col_map['type'] else ""
            
            # Normalize
            val_date = parse_date(raw_date)
            amount = parse_amount(raw_amt, raw_type)
            ref = raw_ref.strip()
            portfolio_id = raw_portfolio.strip()
            
            if ref.lower() in ['nan', 'none', 'null']: ref = ""
            if portfolio_id.lower() in ['nan', 'none', 'null']: portfolio_id = ""
            
            # Track all missing fields
            missing_fields = []
            if not val_date:
                missing_fields.append("Date")
            if amount is None:
                missing_fields.append("Amount")
            if not portfolio_id:
                missing_fields.append("Portfolio ID")
            if not ref:
                missing_fields.append("Reference No.")
            
            # Generate validation error message
            validation_error = None
            if len(missing_fields) == 1:
                validation_error = f"Missing {missing_fields[0]}"
            elif len(missing_fields) > 1:
                validation_error = f"Missing Data ({', '.join(missing_fields)})"
            else:
                validation_error = None
                
            entries.append({
                "value_date": val_date,
                "portfolio_id": portfolio_id,
                "reference_no": ref,
                "amount_signed": amount if amount is not None else Decimal("0.00"),
                "type_raw": raw_type,
                "validation_error": validation_error,
                "raw_data": row.to_dict()
            })
            
        return entries

class CashArCsvParser:
    """
    Parses Cash/AR CSV files.
    Expected Columns: Value Date, Portfolio ID, Vch ID, Amount, Transaction Name
    """
    def __init__(self, source: str = "BOTH"):
        self.source = source

    def parse(self, file_content: bytes) -> List[Dict]:
        try:
            df = pd.read_csv(io.BytesIO(file_content))
        except Exception as e:
            return []
        
        # Normalize headers
        df.columns = [str(c).strip().replace('"', '').replace('.', '') for c in df.columns]
        
        # Column Intepretation Helper
        def find_col(keywords):
            for k in keywords:
                found = next((c for c in df.columns if k.lower() in c.lower()), None)
                if found: return found
            return None

        # Define keywords based on source
        if self.source == "CASH":
            amt_keywords = ['Debit_Amount', 'Debit', 'Amount', 'Value', 'DB_amount', 'DB']
        elif self.source == "AR":
            amt_keywords = ['Credit_Amount', 'Credit', 'Amount', 'Value']
        else:
            amt_keywords = ['Debit_Amount', 'Credit_Amount', 'Amount', 'Debit', 'Credit', 'Value']

        col_map = {
            'date': find_col(['Val_Date', 'Date', 'Time']),
            'portfolio': find_col(['Portfolio_ID', 'Portfolio', 'Client Code']),
            'vch_id': find_col(['Vch_ID', 'Vch', 'Voucher', 'Ref']),
            'amt': find_col(amt_keywords),
            'txn_name': find_col(['Transaction_Name', 'Transaction', 'Description', 'Narration', 'Particulars'])
        }
        
        entries = []
        for _, row in df.iterrows():
            # Extract Raw
            raw_date = str(row[col_map['date']]) if col_map['date'] else ""
            raw_portfolio = str(row[col_map['portfolio']]) if col_map['portfolio'] else ""
            raw_vch = str(row[col_map['vch_id']]) if col_map['vch_id'] else ""
            raw_amt = str(row[col_map['amt']]) if col_map['amt'] else ""
            raw_txn = str(row[col_map['txn_name']]) if col_map['txn_name'] else ""
            
            # Normalize
            val_date = parse_date(raw_date)
            
            # Amount Logic (handle commas etc)
            try:
                clean_amt = raw_amt.replace(',', '').replace('$', '').strip()
                if not clean_amt:
                    amount = None
                else:
                    amount = Decimal(clean_amt)
                    if amount.is_nan():
                        amount = None
            except:
                amount = None
                
            portfolio_id = raw_portfolio.strip()
            vch_id = raw_vch.strip()
            txn_name = raw_txn.strip()
            
            # Handle potential float conversion artifacts in IDs (e.g. "123.0")
            if portfolio_id.endswith('.0'): portfolio_id = portfolio_id[:-2]
            if vch_id.endswith('.0'): vch_id = vch_id[:-2]
            
            # Normalize nan/None/null strings to empty (pandas reads missing cells as 'nan')
            if portfolio_id.lower() in ['nan', 'none', 'null', '']: portfolio_id = ''
            if vch_id.lower() in ['nan', 'none', 'null', '']: vch_id = ''
            if txn_name.lower() in ['nan', 'none', 'null']: txn_name = ''
            
            # Validation — emit standardized codes stored in staging validation_error column
            missing = []
            if not val_date:
                missing.append("Missing_Date")
            if not portfolio_id:
                missing.append("Missing_Portfolio_ID")
            if amount is None:
                missing.append("Missing_Amount")
            if not vch_id:
                missing.append("Missing_VCH_ID")
            
            validation_error = " | ".join(missing) if missing else None
            
            entries.append({
                "value_date": val_date,
                "portfolio_id": portfolio_id,
                "vch_id": vch_id,
                "amount": amount,   # None when missing — stored as NULL in staging
                "transaction_name": txn_name,
                "validation_error": validation_error,
                "raw_data": row.to_dict()
            })
            
        return entries

class CashApCsvParser:
    """
    Parses Cash/AP CSV files for Cash vs AP (Payables) reconciliation.
    Cash Ledger columns:  Portfolio_ID, Val_date, Vch_Id, Transaction_Name, Credit_Amount
    Payable columns:      Portfolio_ID, Val_Date, Vch_Id, Transaction_Name, DB_Amount
    """
    def __init__(self, source: str = "BOTH"):
        self.source = source

    def parse(self, file_content: bytes) -> List[Dict]:
        try:
            df = pd.read_csv(io.BytesIO(file_content))
        except Exception:
            return []

        # Normalize headers
        df.columns = [str(c).strip().replace('"', '').replace('.', '') for c in df.columns]

        def find_col(keywords):
            for k in keywords:
                found = next((c for c in df.columns if k.lower() in c.lower()), None)
                if found:
                    return found
            return None

        # Amount column keywords differ by source
        if self.source == "CASH":
            amt_keywords = ['Credit_Amount', 'Credit', 'Amount', 'Value']
        elif self.source == "PAYABLE":
            amt_keywords = ['DB_Amount', 'Debit_Amount', 'Debit', 'Amount', 'Value']
        else:
            amt_keywords = ['Credit_Amount', 'DB_Amount', 'Debit_Amount', 'Credit', 'Debit', 'Amount', 'Value']

        col_map = {
            'date': find_col(['Val_date', 'Val_Date', 'Date', 'Time']),
            'portfolio': find_col(['Portfolio_ID', 'Portfolio', 'Client Code']),
            'vch_id': find_col(['Vch_Id', 'Vch_ID', 'Vch', 'Voucher', 'Ref']),
            'amt': find_col(amt_keywords),
            'txn_name': find_col(['Transaction_Name', 'Transaction', 'Description', 'Narration', 'Particulars'])
        }

        entries = []
        for _, row in df.iterrows():
            raw_date = str(row[col_map['date']]) if col_map['date'] else ""
            raw_portfolio = str(row[col_map['portfolio']]) if col_map['portfolio'] else ""
            raw_vch = str(row[col_map['vch_id']]) if col_map['vch_id'] else ""
            raw_amt = str(row[col_map['amt']]) if col_map['amt'] else ""
            raw_txn = str(row[col_map['txn_name']]) if col_map['txn_name'] else ""

            val_date = parse_date(raw_date)

            # Amount parsing (no sign flip — amounts are always positive in these CSVs)
            try:
                clean_amt = raw_amt.replace(',', '').replace('$', '').strip()
                if not clean_amt:
                    amount = None
                else:
                    amount = Decimal(clean_amt)
                    if amount.is_nan():
                        amount = None
            except Exception:
                amount = None

            portfolio_id = raw_portfolio.strip()
            vch_id = raw_vch.strip()
            txn_name = raw_txn.strip()

            # Normalize float artifacts and nan strings
            if portfolio_id.endswith('.0'): portfolio_id = portfolio_id[:-2]
            if vch_id.endswith('.0'): vch_id = vch_id[:-2]
            if portfolio_id.lower() in ['nan', 'none', 'null', '']: portfolio_id = ''
            if vch_id.lower() in ['nan', 'none', 'null', '']: vch_id = ''
            if txn_name.lower() in ['nan', 'none', 'null']: txn_name = ''

            # Validation flags
            missing = []
            if not val_date:
                missing.append("Missing_Date")
            if not portfolio_id:
                missing.append("Missing_Portfolio_ID")
            if amount is None:
                missing.append("Missing_Amount")
            if not vch_id:
                missing.append("Missing_VCH_ID")

            validation_error = " | ".join(missing) if missing else None

            entries.append({
                "value_date": val_date,
                "portfolio_id": portfolio_id,
                "vch_id": vch_id,
                "amount": amount,
                "transaction_name": txn_name,
                "validation_error": validation_error,
                "raw_data": row.to_dict()
            })

        return entries


class StockSummaryCsvParser:
    """
    Parses Stock Summary (PMS) CSV.
    Expected Columns: Portfolio_ID, Symbol, Stock_Name, Qty
    Exception: Qty is missing -> validation_error = "Missing_Qty"
    """
    def parse(self, file_content: bytes) -> List[Dict]:
        try:
            df = pd.read_csv(io.BytesIO(file_content))
        except Exception:
            return []

        # Normalize headers
        df.columns = [str(c).strip().replace('"', '').replace('.', '') for c in df.columns]

        def find_col(keywords):
            for k in keywords:
                found = next((c for c in df.columns if k.lower() in c.lower()), None)
                if found:
                    return found
            return None

        col_map = {
            'portfolio': find_col(['Portfolio_ID', 'Portfolio', 'Client Code', 'ClientID']),
            'symbol': find_col(['Symbol', 'Scrip', 'ISIN', 'StockCode', 'Stock_Code']),
            'stock_name': find_col(['Stock_Name', 'StockName', 'Name', 'Description', 'Company']),
            'qty': find_col(['Qty', 'Quantity', 'Holding', 'Units', 'Balance', 'Shares']),
        }

        entries = []
        for _, row in df.iterrows():
            raw_portfolio = str(row[col_map['portfolio']]) if col_map['portfolio'] else ''
            raw_symbol = str(row[col_map['symbol']]) if col_map['symbol'] else ''
            raw_stock_name = str(row[col_map['stock_name']]) if col_map['stock_name'] else ''
            raw_qty = str(row[col_map['qty']]) if col_map['qty'] else ''

            # Normalize strings
            portfolio_id = raw_portfolio.strip()
            symbol = raw_symbol.strip()
            stock_name = raw_stock_name.strip()

            if portfolio_id.endswith('.0'): portfolio_id = portfolio_id[:-2]
            if symbol.endswith('.0'): symbol = symbol[:-2]
            for bad in ['nan', 'none', 'null', '']:
                if portfolio_id.lower() == bad: portfolio_id = ''
                if symbol.lower() == bad: symbol = ''
                if stock_name.lower() == bad: stock_name = ''

            # Parse Qty
            try:
                clean_qty = raw_qty.replace(',', '').strip()
                if not clean_qty or clean_qty.lower() in ['nan', 'none', 'null']:
                    qty = None
                else:
                    qty = Decimal(clean_qty)
                    if qty.is_nan():
                        qty = None
            except Exception:
                qty = None

            # Validation
            missing = []
            if not portfolio_id:
                missing.append("Missing_Portfolio_ID")
            if not symbol:
                missing.append("Missing_Symbol")
            if qty is None:
                missing.append("Missing_Qty")

            validation_error = " | ".join(missing) if missing else None

            entries.append({
                "portfolio_id": portfolio_id,
                "symbol": symbol,
                "stock_name": stock_name,
                "qty": qty,
                "validation_error": validation_error,
                "raw_data": row.to_dict()
            })

        return entries


class TransHistoryCsvParser:
    """
    Parses Transaction History (Meroshare) CSV.
    Expected Columns: Portfolio_ID, Scrip, Transaction_Date, Balance_After_Transaction
    Note: Exception for missing Balance is handled at the engine level (latest date check),
          but we still flag missing required fields at parse time.
    """
    def parse(self, file_content: bytes) -> List[Dict]:
        try:
            df = pd.read_csv(io.BytesIO(file_content))
        except Exception:
            return []

        # Normalize headers
        df.columns = [str(c).strip().replace('"', '').replace('.', '') for c in df.columns]

        def find_col(keywords):
            for k in keywords:
                found = next((c for c in df.columns if k.lower() in c.lower()), None)
                if found:
                    return found
            return None

        col_map = {
            'portfolio': find_col(['Portfolio_ID', 'Portfolio', 'Client Code', 'ClientID', 'ClientCode']),
            'scrip': find_col(['Scrip', 'Symbol', 'StockCode', 'ISIN', 'Stock_Code']),
            'txn_date': find_col(['Transaction_Date', 'TransactionDate', 'Txn_Date', 'TxnDate', 'Date', 'Val_Date']),
            'balance': find_col(['Balance_After_Transaction', 'BalanceAfterTransaction', 'Balance', 'Closing_Balance', 'ClosingBalance']),
        }

        entries = []
        for _, row in df.iterrows():
            raw_portfolio = str(row[col_map['portfolio']]) if col_map['portfolio'] else ''
            raw_scrip = str(row[col_map['scrip']]) if col_map['scrip'] else ''
            raw_date = str(row[col_map['txn_date']]) if col_map['txn_date'] else ''
            raw_balance = str(row[col_map['balance']]) if col_map['balance'] else ''

            # Normalize
            portfolio_id = raw_portfolio.strip()
            scrip = raw_scrip.strip()

            if portfolio_id.endswith('.0'): portfolio_id = portfolio_id[:-2]
            if scrip.endswith('.0'): scrip = scrip[:-2]
            for bad in ['nan', 'none', 'null', '']:
                if portfolio_id.lower() == bad: portfolio_id = ''
                if scrip.lower() == bad: scrip = ''

            # Parse date
            txn_date = parse_date(raw_date)

            # Parse balance
            try:
                clean_bal = raw_balance.replace(',', '').strip()
                if not clean_bal or clean_bal.lower() in ['nan', 'none', 'null']:
                    balance = None
                else:
                    balance = Decimal(clean_bal)
                    if balance.is_nan():
                        balance = None
            except Exception:
                balance = None

            # Validation flags (parse-time)
            missing = []
            if not portfolio_id:
                missing.append("Missing_Portfolio_ID")
            if not scrip:
                missing.append("Missing_Scrip")
            if not txn_date:
                missing.append("Missing_Date")

            validation_error = " | ".join(missing) if missing else None

            entries.append({
                "portfolio_id": portfolio_id,
                "scrip": scrip,
                "transaction_date": txn_date,
                "balance_after_transaction": balance,
                "validation_error": validation_error,
                "raw_data": row.to_dict()
            })

        return entries


class StockAcquisitionCsvParser:
    """
    Parses Stock Acquisitions CSV for Movement Acquisition reconciliation.
    Expected Columns: Portfolio_ID, Scrip, Qty
    (Stock_Name is optional but stored if present)
    Exception rule: Qty missing → validation_error = "Missing_Qty"
    """
    def parse(self, file_content: bytes) -> List[Dict]:
        try:
            df = pd.read_csv(io.BytesIO(file_content))
        except Exception:
            return []

        df.columns = [str(c).strip().replace('"', '').replace('.', '') for c in df.columns]

        def find_col(keywords):
            for k in keywords:
                found = next((c for c in df.columns if k.lower() in c.lower()), None)
                if found:
                    return found
            return None

        col_map = {
            'portfolio': find_col(['Portfolio_ID', 'Portfolio', 'Client Code', 'ClientID']),
            'scrip':     find_col(['Scrip', 'Symbol', 'Stock_Code', 'ISIN']),
            'stock_name': find_col(['Stock_Name', 'StockName', 'Name', 'Description', 'Company']),
            'qty':       find_col(['Qty', 'Quantity', 'Units', 'Shares', 'Holding', 'Balance']),
        }

        entries = []
        for _, row in df.iterrows():
            raw_portfolio  = str(row[col_map['portfolio']]) if col_map['portfolio'] else ''
            raw_scrip      = str(row[col_map['scrip']]) if col_map['scrip'] else ''
            raw_stock_name = str(row[col_map['stock_name']]) if col_map['stock_name'] else ''
            raw_qty        = str(row[col_map['qty']]) if col_map['qty'] else ''

            portfolio_id = raw_portfolio.strip()
            scrip        = raw_scrip.strip()
            stock_name   = raw_stock_name.strip()

            if portfolio_id.endswith('.0'): portfolio_id = portfolio_id[:-2]
            if scrip.endswith('.0'):        scrip = scrip[:-2]

            for bad in ['nan', 'none', 'null', '']:
                if portfolio_id.lower() == bad: portfolio_id = ''
                if scrip.lower() == bad:        scrip = ''
                if stock_name.lower() == bad:   stock_name = ''

            # Parse Qty
            try:
                clean_qty = raw_qty.replace(',', '').strip()
                if not clean_qty or clean_qty.lower() in ['nan', 'none', 'null']:
                    qty = None
                else:
                    qty = Decimal(clean_qty)
                    if qty.is_nan():
                        qty = None
            except Exception:
                qty = None

            missing = []
            if not portfolio_id:
                missing.append("Missing_Portfolio_ID")
            if not scrip:
                missing.append("Missing_Scrip")
            if qty is None:
                missing.append("Missing_Qty")

            validation_error = " | ".join(missing) if missing else None

            entries.append({
                "portfolio_id": portfolio_id,
                "scrip": scrip,
                "stock_name": stock_name,
                "qty": qty,
                "validation_error": validation_error,
            })

        return entries


class AcqTransHistoryCsvParser:
    """
    Parses Transaction History CSV for Movement Acquisition reconciliation.
    Expected Columns: Portfolio_ID, Scrip, Transaction_Date, Credit_Quantity
    Exception rule: missing Credit_Quantity on latest date row is handled in engine.
    Parse-time flags: Missing Portfolio_ID, Missing Scrip, Missing Date.
    """
    def parse(self, file_content: bytes) -> List[Dict]:
        try:
            df = pd.read_csv(io.BytesIO(file_content))
        except Exception:
            return []

        df.columns = [str(c).strip().replace('"', '').replace('.', '') for c in df.columns]

        def find_col(keywords):
            for k in keywords:
                found = next((c for c in df.columns if k.lower() in c.lower()), None)
                if found:
                    return found
            return None

        col_map = {
            'portfolio':  find_col(['Portfolio_ID', 'Portfolio', 'Client Code', 'ClientID', 'ClientCode']),
            'scrip':      find_col(['Scrip', 'Symbol', 'StockCode', 'ISIN', 'Stock_Code']),
            'txn_date':   find_col(['Transaction_Date', 'TransactionDate', 'Txn_Date', 'TxnDate', 'Date', 'Val_Date']),
            'credit_qty': find_col(['Credit_Quantity', 'CreditQuantity', 'Credit_Qty', 'CreditQty',
                                    'Credit', 'Buy_Qty', 'BuyQty', 'Purchased_Qty']),
        }

        entries = []
        for _, row in df.iterrows():
            raw_portfolio  = str(row[col_map['portfolio']]) if col_map['portfolio'] else ''
            raw_scrip      = str(row[col_map['scrip']]) if col_map['scrip'] else ''
            raw_date       = str(row[col_map['txn_date']]) if col_map['txn_date'] else ''
            raw_credit_qty = str(row[col_map['credit_qty']]) if col_map['credit_qty'] else ''

            portfolio_id = raw_portfolio.strip()
            scrip        = raw_scrip.strip()

            if portfolio_id.endswith('.0'): portfolio_id = portfolio_id[:-2]
            if scrip.endswith('.0'):        scrip = scrip[:-2]

            for bad in ['nan', 'none', 'null', '']:
                if portfolio_id.lower() == bad: portfolio_id = ''
                if scrip.lower() == bad:        scrip = ''

            txn_date = parse_date(raw_date)

            # Parse credit quantity
            try:
                clean_cq = raw_credit_qty.replace(',', '').strip()
                if not clean_cq or clean_cq.lower() in ['nan', 'none', 'null']:
                    credit_quantity = None
                else:
                    credit_quantity = Decimal(clean_cq)
                    if credit_quantity.is_nan():
                        credit_quantity = None
            except Exception:
                credit_quantity = None

            missing = []
            if not portfolio_id:
                missing.append("Missing_Portfolio_ID")
            if not scrip:
                missing.append("Missing_Scrip")
            if not txn_date:
                missing.append("Missing_Date")

            validation_error = " | ".join(missing) if missing else None

            entries.append({
                "portfolio_id": portfolio_id,
                "scrip": scrip,
                "transaction_date": txn_date,
                "credit_quantity": credit_quantity,
                "validation_error": validation_error,
            })

        return entries


class StockLiquidationCsvParser:
    """
    Parses Stock Liquidation CSV for Movement Liquidation reconciliation.
    Expected Columns: Portfolio_ID, Scrip, Qty
    (Stock_Name is optional but stored if present)
    Exception rule: Qty missing → validation_error = "Missing_Qty"
    """
    def parse(self, file_content: bytes) -> List[Dict]:
        try:
            df = pd.read_csv(io.BytesIO(file_content))
        except Exception:
            return []

        df.columns = [str(c).strip().replace('"', '').replace('.', '') for c in df.columns]

        def find_col(keywords):
            for k in keywords:
                found = next((c for c in df.columns if k.lower() in c.lower()), None)
                if found:
                    return found
            return None

        col_map = {
            'portfolio':  find_col(['Portfolio_ID', 'Portfolio', 'Client Code', 'ClientID']),
            'scrip':      find_col(['Scrip', 'Symbol', 'Stock_Code', 'ISIN']),
            'stock_name': find_col(['Stock_Name', 'StockName', 'Name', 'Description', 'Company']),
            'qty':        find_col(['Qty', 'Quantity', 'Units', 'Shares', 'Holding', 'Balance']),
        }

        entries = []
        for _, row in df.iterrows():
            raw_portfolio  = str(row[col_map['portfolio']]) if col_map['portfolio'] else ''
            raw_scrip      = str(row[col_map['scrip']]) if col_map['scrip'] else ''
            raw_stock_name = str(row[col_map['stock_name']]) if col_map['stock_name'] else ''
            raw_qty        = str(row[col_map['qty']]) if col_map['qty'] else ''

            portfolio_id = raw_portfolio.strip()
            scrip        = raw_scrip.strip()
            stock_name   = raw_stock_name.strip()

            if portfolio_id.endswith('.0'): portfolio_id = portfolio_id[:-2]
            if scrip.endswith('.0'):        scrip = scrip[:-2]

            for bad in ['nan', 'none', 'null', '']:
                if portfolio_id.lower() == bad: portfolio_id = ''
                if scrip.lower() == bad:        scrip = ''
                if stock_name.lower() == bad:   stock_name = ''

            # Parse Qty
            try:
                clean_qty = raw_qty.replace(',', '').strip()
                if not clean_qty or clean_qty.lower() in ['nan', 'none', 'null']:
                    qty = None
                else:
                    qty = Decimal(clean_qty)
                    if qty.is_nan():
                        qty = None
            except Exception:
                qty = None

            missing = []
            if not portfolio_id:
                missing.append("Missing_Portfolio_ID")
            if not scrip:
                missing.append("Missing_Scrip")
            if qty is None:
                missing.append("Missing_Qty")

            validation_error = " | ".join(missing) if missing else None

            entries.append({
                "portfolio_id": portfolio_id,
                "scrip":        scrip,
                "stock_name":   stock_name,
                "qty":          qty,
                "validation_error": validation_error,
            })

        return entries


class LiqTransHistoryCsvParser:
    """
    Parses Transaction History CSV for Movement Liquidation reconciliation.
    Expected Columns: Portfolio_ID, Scrip, Transaction_Date, Debit_Quantity
    Exception rule: missing Debit_Quantity on any row in a group is handled in engine.
    Parse-time flags: Missing Portfolio_ID, Missing Scrip, Missing Date.
    """
    def parse(self, file_content: bytes) -> List[Dict]:
        try:
            df = pd.read_csv(io.BytesIO(file_content))
        except Exception:
            return []

        df.columns = [str(c).strip().replace('"', '').replace('.', '') for c in df.columns]

        def find_col(keywords):
            for k in keywords:
                found = next((c for c in df.columns if k.lower() in c.lower()), None)
                if found:
                    return found
            return None

        col_map = {
            'portfolio': find_col(['Portfolio_ID', 'Portfolio', 'Client Code', 'ClientID', 'ClientCode']),
            'scrip':     find_col(['Scrip', 'Symbol', 'StockCode', 'ISIN', 'Stock_Code']),
            'txn_date':  find_col(['Transaction_Date', 'TransactionDate', 'Txn_Date', 'TxnDate', 'Date', 'Val_Date']),
            'debit_qty': find_col(['Debit_Quantity', 'DebitQuantity', 'Debit_Qty', 'DebitQty',
                                   'Debit', 'Sell_Qty', 'SellQty', 'Sold_Qty', 'SoldQty']),
        }

        entries = []
        for _, row in df.iterrows():
            raw_portfolio = str(row[col_map['portfolio']]) if col_map['portfolio'] else ''
            raw_scrip     = str(row[col_map['scrip']]) if col_map['scrip'] else ''
            raw_date      = str(row[col_map['txn_date']]) if col_map['txn_date'] else ''
            raw_debit_qty = str(row[col_map['debit_qty']]) if col_map['debit_qty'] else ''

            portfolio_id = raw_portfolio.strip()
            scrip        = raw_scrip.strip()

            if portfolio_id.endswith('.0'): portfolio_id = portfolio_id[:-2]
            if scrip.endswith('.0'):        scrip = scrip[:-2]

            for bad in ['nan', 'none', 'null', '']:
                if portfolio_id.lower() == bad: portfolio_id = ''
                if scrip.lower() == bad:        scrip = ''

            txn_date = parse_date(raw_date)

            # Parse debit quantity
            try:
                clean_dq = raw_debit_qty.replace(',', '').strip()
                if not clean_dq or clean_dq.lower() in ['nan', 'none', 'null']:
                    debit_quantity = None
                else:
                    debit_quantity = Decimal(clean_dq)
                    if debit_quantity.is_nan():
                        debit_quantity = None
            except Exception:
                debit_quantity = None

            missing = []
            if not portfolio_id:
                missing.append("Missing_Portfolio_ID")
            if not scrip:
                missing.append("Missing_Scrip")
            if not txn_date:
                missing.append("Missing_Date")

            validation_error = " | ".join(missing) if missing else None

            entries.append({
                "portfolio_id":    portfolio_id,
                "scrip":           scrip,
                "transaction_date": txn_date,
                "debit_quantity":  debit_quantity,
                "validation_error": validation_error,
            })

        return entries
