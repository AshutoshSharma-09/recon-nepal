from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from decimal import Decimal

from ..models import (
    CAP_recon_batches, CAP_recon_matches, CAP_recon_findings,
    CAP_staging_Cash_entries, CAP_staging_Payable_entries,
    BatchStatus, MatchKind, FindingType, FindingSide,
    CAP_recon_matches_trail, CAP_recon_findings_trail
)


class CapReconEngine:
    def __init__(self, db: Session):
        self.db = db

    def run_batch(self, cash_file_id: int, payable_file_id: int, actor_id: str,
                  tolerance_amount: float = 0.0, date_window_days: int = 0) -> int:
        """
        Creates a new batch and runs Cash vs AP reconciliation.
        Returns the batch_id.
        """
        batch = CAP_recon_batches(
            cash_file_id=cash_file_id,
            payable_file_id=payable_file_id,
            status=BatchStatus.RUNNING
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        self.run_batch_existing(batch.id, cash_file_id, payable_file_id, actor_id, tolerance_amount, date_window_days)
        return batch.id

    def run_batch_existing(self, batch_id: int, cash_file_id: int, payable_file_id: int, actor_id: str,
                           tolerance_amount: float = 0.0, date_window_days: int = 0):
        """
        Runs the full reconciliation logic for an existing batch.
        Matching key: (Portfolio_ID, Val_Date, Vch_Id, abs(amount))
        Amount fields: Credit_Amount (Cash) <-> DB_Amount (Payable)
        Transaction name rule: 'payment' (Cash) <-> 'payment' (Payable), case-insensitive
        Fallback: exact transaction name match
        """
        batch = self.db.query(CAP_recon_batches).filter(CAP_recon_batches.id == batch_id).first()
        if not batch:
            raise Exception(f"Batch {batch_id} not found")

        try:
            # 2. Fetch Staging Data
            cash_entries = self.db.query(CAP_staging_Cash_entries).filter(
                CAP_staging_Cash_entries.file_id == cash_file_id
            ).all()

            payable_entries = self.db.query(CAP_staging_Payable_entries).filter(
                CAP_staging_Payable_entries.file_id == payable_file_id
            ).all()

            matched_cash_ids = set()
            matched_payable_ids = set()

            # --- 3. EXCEPTION HANDLING ---
            def is_exception(entry):
                return bool(entry.validation_error)

            def get_exception_reason(entry):
                return entry.validation_error or "Invalid Data"

            for c in cash_entries:
                if is_exception(c):
                    self._create_finding(batch.id, FindingSide.CASH, c.id, FindingType.EXCEPTION,
                                         get_exception_reason(c), c.portfolio_id, actor_id)
                    matched_cash_ids.add(c.id)

            for p in payable_entries:
                if is_exception(p):
                    self._create_finding(batch.id, FindingSide.PAYABLE, p.id, FindingType.EXCEPTION,
                                         get_exception_reason(p), p.portfolio_id, actor_id)
                    matched_payable_ids.add(p.id)

            # --- 4. AUTO MATCHING O(N) ---
            # Build hash map using PAYABLE entries
            # Key: (Portfolio_ID, Val_Date, Vch_Id, abs(DB_Amount))
            payable_lookup: Dict[Tuple, List[CAP_staging_Payable_entries]] = {}

            for p in payable_entries:
                if p.id in matched_payable_ids:
                    continue
                if p.debit_amount is None:
                    continue
                key = (
                    p.portfolio_id.strip() if p.portfolio_id else "",
                    p.value_date,
                    p.vch_id.strip() if p.vch_id else "",
                    abs(float(p.debit_amount))
                )
                if key not in payable_lookup:
                    payable_lookup[key] = []
                payable_lookup[key].append(p)

            # Iterate Cash entries
            for c in cash_entries:
                if c.id in matched_cash_ids:
                    continue
                if c.credit_amount is None:
                    continue

                key = (
                    c.portfolio_id.strip() if c.portfolio_id else "",
                    c.value_date,
                    c.vch_id.strip() if c.vch_id else "",
                    abs(float(c.credit_amount))
                )

                if key in payable_lookup and payable_lookup[key]:
                    match_candidate = None
                    candidate_index = -1

                    c_txn = (c.transaction_name or "").strip().lower()

                    # Rule 1: Both sides have 'payment' transaction name (case-insensitive)
                    for i, candidate in enumerate(payable_lookup[key]):
                        p_txn = (candidate.transaction_name or "").strip().lower()
                        if c_txn == "payment" and p_txn == "payment":
                            match_candidate = candidate
                            candidate_index = i
                            break

                    # Rule 2: Fallback — exact transaction name match on both sides
                    if not match_candidate:
                        for i, candidate in enumerate(payable_lookup[key]):
                            p_txn = (candidate.transaction_name or "").strip().lower()
                            if c_txn == p_txn:
                                match_candidate = candidate
                                candidate_index = i
                                break

                    if match_candidate:
                        self._create_match(
                            batch.id, c.id, match_candidate.id,
                            MatchKind.AUTO, "Auto Match (Key+Txn)", actor_id,
                            match_candidate.portfolio_id
                        )
                        matched_cash_ids.add(c.id)
                        matched_payable_ids.add(match_candidate.id)
                        payable_lookup[key].pop(candidate_index)

            # --- 4.5 TOLERANCE-BASED MATCH ---
            if tolerance_amount > 0 or date_window_days > 0:
                payable_tolerance_lookup: Dict[Tuple, List] = {}
                for p in payable_entries:
                    if p.id in matched_payable_ids:
                        continue
                    if p.debit_amount is None:
                        continue
                    key = (
                        p.portfolio_id.strip() if p.portfolio_id else "",
                        p.vch_id.strip() if p.vch_id else ""
                    )
                    if key not in payable_tolerance_lookup:
                        payable_tolerance_lookup[key] = []
                    payable_tolerance_lookup[key].append(p)

                for c in cash_entries:
                    if c.id in matched_cash_ids:
                        continue
                    if c.credit_amount is None:
                        continue

                    key = (
                        c.portfolio_id.strip() if c.portfolio_id else "",
                        c.vch_id.strip() if c.vch_id else ""
                    )
                    if key not in payable_tolerance_lookup:
                        continue

                    c_txn = (c.transaction_name or "").strip().lower()

                    for i, p in enumerate(payable_tolerance_lookup[key]):
                        p_txn = (p.transaction_name or "").strip().lower()

                        txn_ok = (
                            (c_txn == "payment" and p_txn == "payment")
                            or (c_txn != "payment" and c_txn == p_txn)
                        )
                        if not txn_ok:
                            continue

                        date_ok = self._dates_within_tolerance(c.value_date, p.value_date, date_window_days)
                        amt_ok = self._amounts_within_tolerance(
                            float(c.credit_amount), float(p.debit_amount), tolerance_amount
                        )

                        if date_ok and amt_ok:
                            reason_parts = []
                            if tolerance_amount > 0:
                                reason_parts.append(f"Amt±{tolerance_amount}")
                            if date_window_days > 0:
                                reason_parts.append(f"Date±{date_window_days}d")
                            reason = f"Tolerance Match ({', '.join(reason_parts)})"

                            self._create_match(
                                batch.id, c.id, p.id,
                                MatchKind.AUTO, reason, actor_id,
                                p.portfolio_id
                            )
                            matched_cash_ids.add(c.id)
                            matched_payable_ids.add(p.id)
                            payable_tolerance_lookup[key].pop(i)
                            break

            # --- 5. UNMATCHED REMAINING ---
            payable_by_portfolio_date: Dict[Tuple, List] = {}
            for p in payable_entries:
                if p.id in matched_payable_ids:
                    continue
                key = (
                    p.portfolio_id.strip() if p.portfolio_id else "",
                    p.value_date
                )
                if key not in payable_by_portfolio_date:
                    payable_by_portfolio_date[key] = []
                payable_by_portfolio_date[key].append(p)

            def get_unmatched_reason_cash(c):
                pid = c.portfolio_id.strip() if c.portfolio_id else ""
                key_pd = (pid, c.value_date)
                candidates = payable_by_portfolio_date.get(key_pd, [])
                if not candidates:
                    return "No matching Portfolio ID / Date in Payable"
                c_vch = (c.vch_id or "").strip()
                c_amt = abs(float(c.credit_amount)) if c.credit_amount is not None else None
                c_txn = (c.transaction_name or "").strip().lower()
                reasons = []
                for p in candidates:
                    p_vch = (p.vch_id or "").strip()
                    p_amt = abs(float(p.debit_amount)) if p.debit_amount is not None else None
                    p_txn = (p.transaction_name or "").strip().lower()
                    if c_vch != p_vch:
                        reasons.append("VCH ID mismatch")
                    if c_amt != p_amt:
                        reasons.append("Amount mismatch")
                    if c_txn == "payment" and p_txn != "payment":
                        reasons.append("Transaction name mismatch (expected Payable: Payment)")
                    elif c_txn != "payment" and c_txn != p_txn:
                        reasons.append("Transaction name mismatch")
                if reasons:
                    return "; ".join(dict.fromkeys(reasons))
                return "No Match"

            def get_unmatched_reason_payable(p):
                pid = p.portfolio_id.strip() if p.portfolio_id else ""
                found_cash = any(
                    (c.id not in matched_cash_ids
                     and (c.portfolio_id or "").strip() == pid
                     and c.value_date == p.value_date)
                    for c in cash_entries
                )
                if not found_cash:
                    return "No matching Portfolio ID / Date in Cash"
                p_vch = (p.vch_id or "").strip()
                p_amt = abs(float(p.debit_amount)) if p.debit_amount is not None else None
                p_txn = (p.transaction_name or "").strip().lower()
                reasons = []
                for c in cash_entries:
                    if c.id in matched_cash_ids:
                        continue
                    c_pid = (c.portfolio_id or "").strip()
                    if c_pid != pid or c.value_date != p.value_date:
                        continue
                    c_vch = (c.vch_id or "").strip()
                    c_amt = abs(float(c.credit_amount)) if c.credit_amount is not None else None
                    c_txn = (c.transaction_name or "").strip().lower()
                    if p_vch != c_vch:
                        reasons.append("VCH ID mismatch")
                    if p_amt != c_amt:
                        reasons.append("Amount mismatch")
                    if c_txn == "payment" and p_txn != "payment":
                        reasons.append("Transaction name mismatch (expected: Payment)")
                    elif c_txn != "payment" and p_txn != c_txn:
                        reasons.append("Transaction name mismatch")
                if reasons:
                    return "; ".join(dict.fromkeys(reasons))
                return "No Match"

            for c in cash_entries:
                if c.id not in matched_cash_ids:
                    reason = get_unmatched_reason_cash(c)
                    self._create_finding(batch.id, FindingSide.CASH, c.id,
                                         FindingType.UNMATCHED, reason, c.portfolio_id, actor_id)

            for p in payable_entries:
                if p.id not in matched_payable_ids:
                    reason = get_unmatched_reason_payable(p)
                    self._create_finding(batch.id, FindingSide.PAYABLE, p.id,
                                         FindingType.UNMATCHED, reason, p.portfolio_id, actor_id)

            batch.status = BatchStatus.COMPLETED
            batch.completed_at = datetime.utcnow()
            self.db.commit()

        except Exception as e:
            self.db.rollback()
            batch = self.db.query(CAP_recon_batches).filter(CAP_recon_batches.id == batch_id).first()
            if batch:
                batch.status = BatchStatus.FAILED
                self.db.commit()
            raise e

        return batch.id

    # ------------------------------------------------------------------ helpers

    def _dates_within_tolerance(self, date1, date2, tolerance_days):
        if tolerance_days == 0:
            return date1 == date2
        if date1 is None or date2 is None:
            return False
        return abs((date1 - date2).days) <= tolerance_days

    def _amounts_within_tolerance(self, amt1, amt2, tolerance):
        if tolerance == 0:
            return abs(amt1) == abs(amt2)
        return abs(abs(amt1) - abs(amt2)) <= tolerance

    def _create_match(self, batch_id, cash_id, payable_id, kind, reason, actor_id, portfolio_id=None):
        now = datetime.utcnow()
        match = CAP_recon_matches(
            batch_id=batch_id,
            cash_entry_id=cash_id,
            payable_entry_id=payable_id,
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

        trail = CAP_recon_matches_trail(
            CAP_recon_match_ID=match.id,
            batch_id=batch_id,
            cash_entry_id=cash_id,
            payable_entry_id=payable_id,
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

        match_id_str = f"PMSCAP{trail.id}"
        match.match_id = match_id_str
        trail.match_id = match_id_str

    def _create_finding(self, batch_id, side, entry_id, kind, reason, portfolio_id=None, actor_id="SYSTEM"):
        now = datetime.utcnow()
        finding = CAP_recon_findings(
            batch_id=batch_id,
            side=side,
            entry_id=entry_id,
            portfolio_id=portfolio_id,
            finding_type=kind,
            finding_reason=reason,
            created_at=now,
            created_by=actor_id,
            Modified_by=actor_id,
            Modified_at=now
        )
        self.db.add(finding)
        self.db.flush()

        trail = CAP_recon_findings_trail(
            CAP_recon_finding_ID=finding.id,
            batch_id=batch_id,
            side=side,
            entry_id=entry_id,
            portfolio_id=portfolio_id,
            finding_type=kind,
            finding_reason=reason,
            created_at=now,
            created_by=actor_id,
            Modified_by=actor_id,
            Modified_at=now,
            Action="CREATED"
        )
        self.db.add(trail)
        self.db.flush()

        self._sync_finding_from_trail(finding.id)

    def _sync_finding_from_trail(self, finding_id):
        latest_trail = self.db.query(CAP_recon_findings_trail).filter(
            CAP_recon_findings_trail.CAP_recon_finding_ID == finding_id
        ).order_by(CAP_recon_findings_trail.id.desc()).first()

        if not latest_trail:
            return

        finding = self.db.query(CAP_recon_findings).filter(
            CAP_recon_findings.id == finding_id
        ).first()

        if finding:
            finding.finding_type = latest_trail.finding_type
            finding.finding_reason = latest_trail.finding_reason
            finding.Modified_by = latest_trail.Modified_by
            finding.Modified_at = latest_trail.Modified_at
            finding.portfolio_id = latest_trail.portfolio_id
