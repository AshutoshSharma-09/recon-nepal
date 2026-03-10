
import requests
import json

API_URL = "http://localhost:8000"
API_KEY = "local-dev-key"

def debug_dissolve():
    headers = {"X-API-Key": API_KEY}
    
    # 1. Get Latest Batch
    resp = requests.get(f"{API_URL}/api/v1/recon/latest", headers=headers)
    if not resp.ok:
        print("Failed to fetch recon:", resp.text)
        return

    data = resp.json()
    batch_id = data.get('batch_id') or data.get('summary', {}).get('batch_id')
    # If standard response is used
    if not batch_id and 'batch_id' in data: 
         batch_id = data['batch_id']
         
    if not batch_id:
        print("No batch ID found in response")
        return

    print(f"Working with Batch ID: {batch_id}")
    
    matched_rows = [r for r in data['bank_records'] if r['match_status'] == 'MATCHED']
    
    split_matches = []
    # FIX: PortfolioID matching might be exact or case sensitive
    for r in matched_rows:
        pid = r.get('PortfolioID') or ''
        if 'NIBLCT869304' in pid:
             split_matches.append(r)
             
    if not split_matches:
        print("No matches found. Creating Manual Split Match for testing...")
        # 1. Find Unmatched 37000 Bank
        unmatched_bk = [r for r in data['bank_records'] if r['match_status'] == 'UNMATCHED']
        # Note: Amount is float or string
        parent_bank = None
        for r in unmatched_bk:
             pid = r.get('PortfolioID') or ''
             if 'NIBLCT869304' in pid:
                 cred = float(r.get('Credit', 0))
                 if abs(cred - 37000) < 1.0:
                     parent_bank = r
                     break
        
        # 2. Find Broker Candidates (12000, 20000, 5000)
        unmatched_br = [r for r in data['broker_records'] if r['match_status'] == 'UNMATCHED']
        cands_br = []
        for r in unmatched_br:
             pid = r.get('PortfolioID') or ''
             if 'NIBLCT869304' in pid:
                  cands_br.append(r)
        
        if not parent_bank:
             print("Cannot create test data: Missing 37000 Bank")
             return
        if len(cands_br) < 1: # We can split 1-to-1 if need be
             print("Cannot create test data: Missing Broker Candidates")
             return

        print(f"Creating split with Bank {parent_bank['id']} and {len(cands_br)} Brokers")

        # 3. Create Split Payload
        payload = {
            "batch_id": batch_id,
            "bank_entry_ids": [int(parent_bank['id'])],
            "broker_entry_ids": [int(c['id']) for c in cands_br], 
            "note": "Debug Split",
            "canonical_reference": f"MAN-SPLIT-DEBUG"
        }
        res = requests.post(f"{API_URL}/api/v1/recon/manual-match", json=payload, headers=headers)
        if not res.ok:
            print("Failed to create split:", res.text)
            return
        print("Created Debug Split Match. Refetching...")
        
        # Refetch
        resp = requests.get(f"{API_URL}/api/v1/recon/latest", headers=headers)
        data = resp.json()
        matched_rows = [r for r in data['bank_records'] if r['match_status'] == 'MATCHED']
        for r in matched_rows:
            if 'NIBLCT869304' in (r.get('PortfolioID') or ''):
                split_matches.append(r)

    print("Found Matches for NIBLCT869304:")
    for m in split_matches:
        # match_id is not in row? frontend computes it. But backend response has it in 'match_id'
        print(f" - ID: {m.get('match_id')} | Amta: {m.get('Credit') or m.get('Debit')}")

    if not split_matches:
        print("Still no matches found after creation attempt??")
        return

    # 3. Trigger Dissolve on the first one
    target = split_matches[0]
    match_id = target.get('match_id')
    
    if not match_id:
        print("Target has no match_id")
        return

    print(f"\nAttempting to Dissolve Match ID: {match_id}")
    
    dissolve_payload = {
        "batch_id": batch_id,
        "match_id": match_id
    }
    
    res = requests.post(f"{API_URL}/api/v1/recon/dissolve-match", json=dissolve_payload, headers=headers)
    
    if res.ok:
         print("Dissolve Request SUCCESS")
    else:
         print(f"Dissolve Request FAILED: {res.text}")
         return

    # 4. Verify Restoration
    # Fetch recon again
    resp2 = requests.get(f"{API_URL}/api/v1/recon/latest", headers=headers)
    data2 = resp2.json()
    
    # Check Unmatched for the original 37000
    unmatched_bk = [r for r in data2['bank_records'] if r['match_status'] == 'UNMATCHED']
    
    found_parent = False
    for r in unmatched_bk:
        if 'NIBLCT869304' in (r.get('PortfolioID') or ''):
             # print(f"Found Potential Parent: {r['Credit']}")
             amt = float(r.get('Credit', 0) or 0)
             if abs(amt - 37000) < 1.0:
                 found_parent = True
                 print("*** PARENT RESTORED SUCCESSFULLY ***") 
                 break 
                 
    if not found_parent:
        print("*** FAILURE: PARENT NOT FOUND IN UNMATCHED ***")

if __name__ == "__main__":
    debug_dissolve()
