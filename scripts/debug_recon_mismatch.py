
import requests
import json

API_URL = "http://localhost:8000"
API_KEY = "local-dev-key"

def debug_recon():
    headers = {"X-API-Key": API_KEY}
    resp = requests.get(f"{API_URL}/api/v1/recon/latest", headers=headers)
    
    with open("debug_out_py.txt", "w", encoding="utf-8") as f:
        def log(msg):
            print(msg)
            f.write(str(msg) + "\n")

        if not resp.ok:
            log(f"Failed to fetch recon: {resp.text}")
            return

        data = resp.json()
        bank_recs = data['bank_records']
        
        log(f"Total Bank Records: {len(bank_recs)}")
        log("ID | Ref | PID | Amt | Status")
        for r in bank_recs:
             log(f"{r['id']} | {r.get('Reference')} | {r.get('PortfolioID')} | {r.get('Credit') or r.get('Debit')} | {r['match_status']}")

if __name__ == "__main__":
    debug_recon()
