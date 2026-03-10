from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from decimal import Decimal

from ..models import (
    CR_recon_batches, CR_recon_matches, CR_recon_findings, 
    CR_staging_Cash_entries, CR_staging_Receivable_entries, 
    BatchStatus, MatchKind, FindingType, FindingSide,
    CR_recon_matches_trail, CR_recon_findings_trail
)

class CarReconEngine:
    def __init__(self, db: Session):
        self.db = db

    def run_batch(self, cash_file_id: int, receivable_file_id: int, actor_id: str, 
                  tolerance_amount: float = 0.0, date_window_days: int = 0) -> int:
        """
        Runs a reconciliation batch between Cash and Receivable files.
        Returns the batch_id.
        """
        # 1. Create Batch
        batch = CR_recon_batches(
            cash_file_id=cash_file_id, 
            receivable_file_id=receivable_file_id,
            status=BatchStatus.RUNNING
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        
        self.run_batch_existing(batch.id, cash_file_id, receivable_file_id, actor_id, tolerance_amount, date_window_days)
        return batch.id

    def run_batch_existing(self, batch_id: int, cash_file_id: int, receivable_file_id: int, actor_id: str, 
                  tolerance_amount: float = 0.0, date_window_days: int = 0):
        """
        Runs logic for an existing batch.
        """
        # Fetch Batch
        batch = self.db.query(CR_recon_batches).filter(CR_recon_batches.id == batch_id).first()
        if not batch: raise Exception(f"Batch {batch_id} not found")
        
        try:
            # 2. Fetch Staging Data
            cash_entries = self.db.query(CR_staging_Cash_entries).filter(
                CR_staging_Cash_entries.file_id == cash_file_id
            ).all()
            
            ar_entries = self.db.query(CR_staging_Receivable_entries).filter(
                CR_staging_Receivable_entries.file_id == receivable_file_id
            ).all()
            
            # Helper to track consumed IDs
            matched_cash_ids = set()
            matched_ar_ids = set()
            
            # --- 3. EXCEPTION HANDLING ---
            # An entry is an exception if its staging validation_error is set
            # (parser flags: Missing_Amount, Missing_VCH_ID, Missing_Date, Missing_Portfolio_ID)
            def is_exception(entry):
                return bool(entry.validation_error)

            def get_exception_reason(entry):
                # Return the validation_error string stored by the parser as-is
                return entry.validation_error or "Invalid Data"

            for c in cash_entries:
                if is_exception(c):
                    self._create_finding(batch.id, FindingSide.CASH, c.id, FindingType.EXCEPTION, get_exception_reason(c), c.portfolio_id)
                    matched_cash_ids.add(c.id)
            
            for r in ar_entries:
                if is_exception(r):
                    self._create_finding(batch.id, FindingSide.RECEIVABLE, r.id, FindingType.EXCEPTION, get_exception_reason(r), r.portfolio_id)
                    matched_ar_ids.add(r.id)


            # --- 4. AUTO MATCHING (O(N)) ---
            # Strategy: Build Hash Map for AR entries
            # Key: (Portfolio_ID, Value_Date, Vch_ID, ABS(Amount))
            
            ar_lookup: Dict[Tuple, List[CR_staging_Receivable_entries]] = {}
            
            for r in ar_entries:
                if r.id in matched_ar_ids: continue
                # Validate Amount exists (already checked in exceptions but safety first)
                if r.cr_amount is None: continue
                
                key = (
                    r.portfolio_id.strip() if r.portfolio_id else "",
                    r.value_date,
                    r.vch_id.strip() if r.vch_id else "",
                    abs(float(r.cr_amount))
                )
                
                if key not in ar_lookup:
                    ar_lookup[key] = []
                ar_lookup[key].append(r)
            
            # Iterate Cash Entries
            for c in cash_entries:
                if c.id in matched_cash_ids: continue
                if c.db_amount is None: continue

                key = (
                    c.portfolio_id.strip() if c.portfolio_id else "",
                    c.value_date,
                    c.vch_id.strip() if c.vch_id else "",
                    abs(float(c.db_amount))
                )
                
                if key in ar_lookup and ar_lookup[key]:
                    # Potential Matches Found by Key (O(1))
                    
                    match_candidate = None
                    candidate_index = -1
                    
                    c_txn = (c.transaction_name or "").strip().lower()
                    
                    # Search specifically for the matching transaction rule first
                    for i, candidate in enumerate(ar_lookup[key]):
                        r_txn = (candidate.transaction_name or "").strip().lower()
                        
                        # Rule: Cash "Sales Charges Apply" <-> AR "Receive"
                        if c_txn == "sales charges apply" and r_txn == "receive":
                            match_candidate = candidate
                            candidate_index = i
                            break
                    
                    # If specific rule didn't match, or not applicable, try exact name match or default match?
                    # User request implies Strict Logic for the specific case.
                    # For now, if no rule match, we can falback to first available if names are ignored OR strict name match?
                    # "transaction name should be in cash CSV (Sales Charges Apply) = AR's CSV (Receive)"
                    # This implies matching logic depends on this. 
                    # If names are DIFFERENT and NOT in the rule, should we match? 
                    # Usually Auto Match requires stricter validation. 
                    # Let's assume:
                    # 1. Start with Strict Rule Mapping
                    # 2. If no rule mapping, try Exact Name Match
                    # 3. If neither, DO NOT MATCH (to be safe and avoid bad auto matches)
                    
                    if not match_candidate:
                        for i, candidate in enumerate(ar_lookup[key]):
                            r_txn = (candidate.transaction_name or "").strip().lower()
                            if c_txn == r_txn:
                                match_candidate = candidate
                                candidate_index = i
                                break
                    
                    # If still no match candidate, we skip auto-match for this entry
                    # (It will end up as UNMATCHED)
                    
                    if match_candidate:
                        # CREATE MATCH
                        self._create_match(
                            batch.id, c.id, match_candidate.id, 
                            MatchKind.AUTO, "Auto Match (Key+Txn)", actor_id, 
                            match_candidate.portfolio_id
                        )
                        matched_cash_ids.add(c.id)
                        matched_ar_ids.add(match_candidate.id)
                        
                        # Remove from lookup to prevent double matching
                        ar_lookup[key].pop(candidate_index)

            # --- 4.5. TOLERANCE-BASED MATCH ---
            # Only run if tolerance/date window is configured
            if tolerance_amount > 0 or date_window_days > 0:
                # Group remaining AR entries by (portfolio_id, vch_id)
                ar_tolerance_lookup: Dict[Tuple, List] = {}
                for r in ar_entries:
                    if r.id in matched_ar_ids: continue
                    if r.cr_amount is None: continue
                    key = (
                        r.portfolio_id.strip() if r.portfolio_id else "",
                        r.vch_id.strip() if r.vch_id else ""
                    )
                    if key not in ar_tolerance_lookup:
                        ar_tolerance_lookup[key] = []
                    ar_tolerance_lookup[key].append(r)

                for c in cash_entries:
                    if c.id in matched_cash_ids: continue
                    if c.db_amount is None: continue

                    key = (
                        c.portfolio_id.strip() if c.portfolio_id else "",
                        c.vch_id.strip() if c.vch_id else ""
                    )
                    if key not in ar_tolerance_lookup:
                        continue

                    c_txn = (c.transaction_name or "").strip().lower()

                    for i, r in enumerate(ar_tolerance_lookup[key]):
                        r_txn = (r.transaction_name or "").strip().lower()

                        # Apply same transaction-name rule
                        txn_ok = (
                            (c_txn == "sales charges apply" and r_txn == "receive")
                            or (c_txn != "sales charges apply" and c_txn == r_txn)
                        )
                        if not txn_ok:
                            continue

                        date_ok = self._dates_within_tolerance(
                            c.value_date, r.value_date, date_window_days
                        )
                        amt_ok = self._amounts_within_tolerance(
                            float(c.db_amount), float(r.cr_amount), tolerance_amount
                        )

                        if date_ok and amt_ok:
                            reason_parts = []
                            if tolerance_amount > 0:
                                reason_parts.append(f"Amt\u00b1{tolerance_amount}")
                            if date_window_days > 0:
                                reason_parts.append(f"Date\u00b1{date_window_days}d")
                            reason = f"Tolerance Match ({', '.join(reason_parts)})"

                            self._create_match(
                                batch.id, c.id, r.id,
                                MatchKind.AUTO, reason, actor_id,
                                r.portfolio_id
                            )
                            matched_cash_ids.add(c.id)
                            matched_ar_ids.add(r.id)
                            ar_tolerance_lookup[key].pop(i)
                            break

            # --- 5. UNMATCHED REMAINING ---
            # Build lookup maps for unmatched reason generation
            ar_by_portfolio_date: Dict[Tuple, List] = {}
            for r in ar_entries:
                if r.id in matched_ar_ids: continue
                key = (
                    r.portfolio_id.strip() if r.portfolio_id else "",
                    r.value_date
                )
                if key not in ar_by_portfolio_date:
                    ar_by_portfolio_date[key] = []
                ar_by_portfolio_date[key].append(r)

            def get_unmatched_reason_cash(c):
                pid = c.portfolio_id.strip() if c.portfolio_id else ""
                key_pd = (pid, c.value_date)
                candidates = ar_by_portfolio_date.get(key_pd, [])
                if not candidates:
                    return "No matching Portfolio ID / Date in AR"
                # There are AR entries with same portfolio+date — check why they didn't match
                c_vch = (c.vch_id or "").strip()
                c_amt = abs(float(c.db_amount)) if c.db_amount is not None else None
                c_txn = (c.transaction_name or "").strip().lower()
                reasons = []
                for r in candidates:
                    r_vch = (r.vch_id or "").strip()
                    r_amt = abs(float(r.cr_amount)) if r.cr_amount is not None else None
                    r_txn = (r.transaction_name or "").strip().lower()
                    if c_vch != r_vch:
                        reasons.append("VCH ID mismatch")
                    if c_amt != r_amt:
                        reasons.append("Amount mismatch")
                    # Transaction name rule
                    if c_txn == "sales charges apply" and r_txn != "receive":
                        reasons.append("Transaction name mismatch (expected AR: Receive)")
                    elif c_txn != "sales charges apply" and c_txn != r_txn:
                        reasons.append("Transaction name mismatch")
                if reasons:
                    return "; ".join(dict.fromkeys(reasons))
                return "No Match"

            def get_unmatched_reason_ar(r):
                pid = r.portfolio_id.strip() if r.portfolio_id else ""
                # Check if any cash entry has same portfolio+date
                found_cash = False
                for c in cash_entries:
                    if c.id in matched_cash_ids: continue
                    c_pid = c.portfolio_id.strip() if c.portfolio_id else ""
                    if c_pid == pid and c.value_date == r.value_date:
                        found_cash = True
                        break
                if not found_cash:
                    return "No matching Portfolio ID / Date in Cash"
                r_vch = (r.vch_id or "").strip()
                r_amt = abs(float(r.cr_amount)) if r.cr_amount is not None else None
                r_txn = (r.transaction_name or "").strip().lower()
                reasons = []
                for c in cash_entries:
                    if c.id in matched_cash_ids: continue
                    c_pid = c.portfolio_id.strip() if c.portfolio_id else ""
                    if c_pid != pid or c.value_date != r.value_date: continue
                    c_vch = (c.vch_id or "").strip()
                    c_amt = abs(float(c.db_amount)) if c.db_amount is not None else None
                    c_txn = (c.transaction_name or "").strip().lower()
                    if r_vch != c_vch:
                        reasons.append("VCH ID mismatch")
                    if r_amt != c_amt:
                        reasons.append("Amount mismatch")
                    if c_txn == "sales charges apply" and r_txn != "receive":
                        reasons.append("Transaction name mismatch (expected: Receive)")
                    elif c_txn != "sales charges apply" and r_txn != c_txn:
                        reasons.append("Transaction name mismatch")
                if reasons:
                    return "; ".join(dict.fromkeys(reasons))
                return "No Match"

            for c in cash_entries:
                if c.id not in matched_cash_ids:
                    reason = get_unmatched_reason_cash(c)
                    self._create_finding(batch.id, FindingSide.CASH, c.id, FindingType.UNMATCHED, reason, c.portfolio_id)
            
            for r in ar_entries:
                if r.id not in matched_ar_ids:
                    reason = get_unmatched_reason_ar(r)
                    self._create_finding(batch.id, FindingSide.RECEIVABLE, r.id, FindingType.UNMATCHED, reason, r.portfolio_id)

            batch.status = BatchStatus.COMPLETED
            batch.completed_at = datetime.utcnow()
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            batch.status = BatchStatus.FAILED
            self.db.commit()
            raise e
            
        return batch.id

    def _dates_within_tolerance(self, date1, date2, tolerance_days):
        """Check if two dates are within tolerance window"""
        if tolerance_days == 0:
            return date1 == date2
        if date1 is None or date2 is None:
            return False
        delta = abs((date1 - date2).days)
        return delta <= tolerance_days

    def _amounts_within_tolerance(self, amt1, amt2, tolerance):
        """Check if two amounts are within tolerance"""
        if tolerance == 0:
            return abs(amt1) == abs(amt2)
        return abs(abs(amt1) - abs(amt2)) <= tolerance

    def _create_match(self, batch_id, cash_id, ar_id, kind, reason, actor_id, portfolio_id=None):
        now = datetime.utcnow()
        match = CR_recon_matches(
            batch_id=batch_id,
            cash_entry_id=cash_id,
            receivable_entry_id=ar_id,
            portfolio_id=portfolio_id,
            match_kind=kind,
            match_id="TEMP",
            reason=reason,
            created_by=actor_id,
            created_at=now,
            Modified_by=actor_id,
            Modified_at=now
        )
        self.db.add(match)
        self.db.flush()

        trail = CR_recon_matches_trail(
            CR_recon_match_ID=match.id,
            batch_id=batch_id,
            cash_entry_id=cash_id,
            receivable_entry_id=ar_id,
            portfolio_id=portfolio_id,
            match_kind=kind,
            match_id="TEMP",
            reason=reason,
            created_by=actor_id,
            created_at=now,
            Modified_by=actor_id,
            Modified_at=now,
            Action="AUTO_MATCH"
        )
        self.db.add(trail)
        self.db.flush()
        
        # PMSCAR + Trail ID
        match_id_str = f"PMSCAR{trail.id}"
        match.match_id = match_id_str
        trail.match_id = match_id_str

    def _create_finding(self, batch_id, side, entry_id, kind, reason, portfolio_id=None, actor_id="SYSTEM"):
        finding = CR_recon_findings(
            batch_id=batch_id,
            side=side,
            entry_id=entry_id,
            portfolio_id=portfolio_id,
            finding_type=kind,
            finding_reason=reason,
            created_at=datetime.utcnow(),
            created_by=actor_id,
            Modified_by=actor_id,
            Modified_at=datetime.utcnow()
        )
        self.db.add(finding)
        self.db.flush()

        trail = CR_recon_findings_trail(
            CR_recon_finding_ID=finding.id,
            batch_id=batch_id,
            side=side,
            entry_id=entry_id,
            portfolio_id=portfolio_id,
            finding_type=kind,
            finding_reason=reason,
            created_at=datetime.utcnow(),
            created_by=actor_id,
            Modified_by=actor_id,
            Modified_at=datetime.utcnow(),
            Action="CREATED"
        )
        self.db.add(trail)
        self.db.flush()
        
        # Sync finding from trail
        self._sync_finding_from_trail(finding.id)
    
    def _sync_finding_from_trail(self, finding_id):
        latest_trail = self.db.query(CR_recon_findings_trail).filter(
            CR_recon_findings_trail.CR_recon_finding_ID == finding_id
        ).order_by(CR_recon_findings_trail.id.desc()).first()
        
        if not latest_trail: return
        
        finding = self.db.query(CR_recon_findings).filter(
            CR_recon_findings.id == finding_id
        ).first()
        
        if finding:
            finding.finding_type = latest_trail.finding_type
            finding.finding_reason = latest_trail.finding_reason
            finding.Modified_by = latest_trail.Modified_by
            finding.Modified_at = latest_trail.Modified_at
            finding.portfolio_id = latest_trail.portfolio_id
