from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Dict, Optional
from datetime import datetime
import logging
import traceback

from ..models import (
    BB_recon_batches, BB_recon_matches, BB_recon_findings, 
    BB_staging_broker_entries, BB_staging_bank_entries, 
    BatchStatus, MatchKind, FindingType, FindingSide
)

logger = logging.getLogger(__name__)

class ReconEngine:
    def __init__(self, db: Session):
        self.db = db

    def run_batch(self, broker_file_id: int, bank_file_id: int, actor_id: str, 
                  tolerance_amount: float = 0.0, date_window_days: int = 0) -> int:
        """
        Runs a reconciliation batch between two files.
        Returns the batch_id.
        """
        # 1. Create Batch
        batch = BB_recon_batches(
            broker_file_id=broker_file_id, 
            bank_file_id=bank_file_id,
            status=BatchStatus.RUNNING
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        
        self.run_batch_existing(batch.id, broker_file_id, bank_file_id, actor_id, tolerance_amount, date_window_days)
        return batch.id

    def run_batch_existing(self, batch_id: int, broker_file_id: int, bank_file_id: int, actor_id: str, 
                  tolerance_amount: float = 0.0, date_window_days: int = 0):
        """
        Runs logic for an existing batch.
        """
        # Fetch Batch
        batch = self.db.query(BB_recon_batches).filter(BB_recon_batches.id == batch_id).first()
        if not batch: raise Exception(f"Batch {batch_id} not found")
        
        try:
            # 2. Fetch Staging Data
            broker_entries = self.db.query(BB_staging_broker_entries).filter(
                BB_staging_broker_entries.file_id == broker_file_id
            ).all()
            
            bank_entries = self.db.query(BB_staging_bank_entries).filter(
                BB_staging_bank_entries.file_id == bank_file_id
            ).all()
            
            logger.info(f"BB RECON: Batch {batch_id} - Broker entries: {len(broker_entries)}, Bank entries: {len(bank_entries)}")
            
            # Helper to track consumed IDs
            matched_broker_ids = set()
            matched_bank_ids = set()
            
            # --- 3. EXCEPTION HANDLING ---
            # Mark invalid rows (Validation Error OR Missing Critical Fields)
            # Critical Fields: Value Date, Amount, Reference
            
            def is_exception(entry):
                if entry.validation_error: return True
                if not entry.value_date: return True
                if entry.amount_signed is None: return True # 0.0 is valid, None is not
                if not entry.reference_no or entry.reference_no.strip() == "": return True
                if not entry.portfolio_id or entry.portfolio_id.strip() == "": return True
                return False
            
            def get_detailed_reason(entry):
                """Generate detailed reason based on missing fields"""
                if entry.validation_error:
                    return entry.validation_error
                
                missing_fields = []
                if not entry.value_date:
                    missing_fields.append("Date")
                if entry.amount_signed is None:
                    missing_fields.append("Amount")
                if not entry.portfolio_id or entry.portfolio_id.strip() == "":
                    missing_fields.append("Portfolio ID")
                if not entry.reference_no or entry.reference_no.strip() == "":
                    missing_fields.append("Reference No.")
                
                if len(missing_fields) == 1:
                    return f"Missing {missing_fields[0]}"
                elif len(missing_fields) > 1:
                    return f"Missing Data ({', '.join(missing_fields)})"
                else:
                    return "Missing Critical Data (Date/Amount/Ref/Portfolio)"

            for b in broker_entries:
                if is_exception(b):
                    reason = get_detailed_reason(b)
                    # Pass portfolio_id even if entry has validation errors
                    self._create_finding(batch.id, FindingSide.BROKER, b.id, FindingType.EXCEPTION, reason, b.portfolio_id)
                    matched_broker_ids.add(b.id)
            
            for k in bank_entries:
                if is_exception(k):
                    reason = get_detailed_reason(k)
                    # Pass portfolio_id even if entry has validation errors
                    self._create_finding(batch.id, FindingSide.BANK, k.id, FindingType.EXCEPTION, reason, k.portfolio_id)
                    matched_bank_ids.add(k.id)
            
            logger.info(f"BB RECON: After exception check - Exceptions: broker={len([b for b in broker_entries if b.id in matched_broker_ids])}, bank={len([k for k in bank_entries if k.id in matched_bank_ids])}")
            
            # Criteria: Value Date AND Amount AND Reference AND Portfolio
            # Optimize: Build lookups? For now, nested loop O(N*M) or Dictionary O(N)
            
            # Dictionary approach: Key = (Date, Amt, Ref, Portfolio)
            bank_lookup = {}
            for k in bank_entries:
                if k.id in matched_bank_ids: continue
                # key must include Portfolio ID
                # User Change: Match on ABSOLUTE amount (ignore sign)
                key = (k.value_date, abs(float(k.amount_signed)), k.reference_no, k.portfolio_id)
                if key not in bank_lookup: bank_lookup[key] = []
                bank_lookup[key].append(k)
                
            for b in broker_entries:
                if b.id in matched_broker_ids: continue
                
                
                # User Change: Match on ABSOLUTE amount
                key = (b.value_date, abs(float(b.amount_signed)), b.reference_no, b.portfolio_id)
                if key in bank_lookup and bank_lookup[key]:
                    # Match Found!
                    bank_match = bank_lookup[key].pop(0) # Take first available
                    
                    self._create_match(batch.id, b.id, bank_match.id, MatchKind.AUTO, "Exact Match", actor_id, bank_match.portfolio_id)
                    
                    matched_broker_ids.add(b.id)
                    matched_bank_ids.add(bank_match.id)

            # --- 4.5. TOLERANCE-BASED EXACT MATCH ---
            # Only run if tolerance is set
            if tolerance_amount > 0 or date_window_days > 0:
                # Rebuild lookup for remaining entries with tolerance
                bank_tolerance_lookup = {}
                for k in bank_entries:
                    if k.id in matched_bank_ids: continue
                    # Group by portfolio and reference (must still match exactly)
                    key = (k.portfolio_id, k.reference_no)
                    if key not in bank_tolerance_lookup:
                        bank_tolerance_lookup[key] = []
                    bank_tolerance_lookup[key].append(k)
                
                for b in broker_entries:
                    if b.id in matched_broker_ids: continue
                    
                    key = (b.portfolio_id, b.reference_no)
                    if key in bank_tolerance_lookup:
                        # Find first bank entry that matches within tolerance
                        for i, bank_match in enumerate(bank_tolerance_lookup[key]):
                            date_match = self._dates_within_tolerance(
                                b.value_date, bank_match.value_date, date_window_days
                            )
                            amount_match = self._amounts_within_tolerance(
                                float(b.amount_signed), 
                                float(bank_match.amount_signed), 
                                tolerance_amount
                            )
                            
                            if date_match and amount_match:
                                # Match found with tolerance
                                reason_parts = []
                                if tolerance_amount > 0:
                                    reason_parts.append(f"Amt±{tolerance_amount}")
                                if date_window_days > 0:
                                    reason_parts.append(f"Date±{date_window_days}d")
                                reason = f"Tolerance Match ({', '.join(reason_parts)})"
                                
                                self._create_match(
                                    batch.id, b.id, bank_match.id, 
                                    MatchKind.AUTO, 
                                    reason,
                                    actor_id, 
                                    bank_match.portfolio_id
                                )
                                matched_broker_ids.add(b.id)
                                matched_bank_ids.add(bank_match.id)
                                # Remove from lookup
                                bank_tolerance_lookup[key].pop(i)
                                break

            # --- 5. LINKABLE (RELAXED) WITH TOLERANCE ---
            # Criteria: Value Date (with tolerance) AND Amount (with tolerance) AND Portfolio (Ref differs)
            # Re-build lookup for remaining
            bank_relaxed = {}
            for k in bank_entries:
                if k.id in matched_bank_ids: continue
                # Loose match still requires Portfolio ID to be correct
                # User Change: Match on ABSOLUTE amount
                key = k.portfolio_id  # Only portfolio, reference can differ
                if key not in bank_relaxed:
                    bank_relaxed[key] = []
                bank_relaxed[key].append(k)
                
            for b in broker_entries:
                if b.id in matched_broker_ids: continue
                
                key = b.portfolio_id
                if key in bank_relaxed:
                    # Find first bank entry that matches within tolerance
                    for i, bank_suggestion in enumerate(bank_relaxed[key]):
                        # Apply tolerance checks
                        date_match = self._dates_within_tolerance(
                            b.value_date, bank_suggestion.value_date, date_window_days
                        )
                        amount_match = self._amounts_within_tolerance(
                            float(b.amount_signed), 
                            float(bank_suggestion.amount_signed), 
                            tolerance_amount
                        )
                        
                        if date_match and amount_match:
                            # Match Found (Linkable)
                            self._create_finding(batch.id, FindingSide.BROKER, b.id, FindingType.LINKABLE, "REF_MISMATCH_LINKABLE", b.portfolio_id)
                            self._create_finding(batch.id, FindingSide.BANK, bank_suggestion.id, FindingType.LINKABLE, "REF_MISMATCH_LINKABLE", bank_suggestion.portfolio_id)
                            
                            matched_broker_ids.add(b.id)
                            matched_bank_ids.add(bank_suggestion.id)
                            # Remove from lookup
                            bank_relaxed[key].pop(i)
                            break

            # --- 6. UNMATCHED REMAINING ---
            for b in broker_entries:
                if b.id not in matched_broker_ids:
                    # Anything not Matched, Exception, or Linkable is Unmatched
                    self._create_finding(batch.id, FindingSide.BROKER, b.id, FindingType.UNMATCHED, "No Auto-Match", b.portfolio_id)

            for k in bank_entries:
                if k.id not in matched_bank_ids:
                    self._create_finding(batch.id, FindingSide.BANK, k.id, FindingType.UNMATCHED, "No Auto-Match", k.portfolio_id)

            logger.info(f"BB RECON: Batch {batch_id} completed successfully. Committing...")
            batch.status = BatchStatus.COMPLETED
            batch.completed_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"BB RECON: Batch {batch_id} committed successfully.")
            
        except Exception as e:
            logger.error(f"BB RECON ERROR: Batch {batch_id} FAILED with exception: {str(e)}")
            logger.error(f"BB RECON ERROR: Full traceback:\n{traceback.format_exc()}")
            self.db.rollback()
            batch = self.db.query(BB_recon_batches).filter(BB_recon_batches.id == batch_id).first()
            if batch:
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

    def _create_match(self, batch_id, broker_id, bank_id, kind, reason, actor_id, portfolio_id=None):
        # Create match record first without match_id
        match = BB_recon_matches(
            batch_id=batch_id,
            broker_entry_id=broker_id,
            bank_entry_id=bank_id,
            portfolio_id=portfolio_id,
            match_kind=kind,
            match_id="TEMP",  # Temporary placeholder
            reason=reason,
            created_by=actor_id
        )
        self.db.add(match)
        self.db.flush() # Get match.id

        # Trail Log
        from ..models import BB_recon_matches_trail
        trail = BB_recon_matches_trail(
            BB_recon_match_ID=match.id,
            batch_id=batch_id,
            broker_entry_id=broker_id,
            bank_entry_id=bank_id,
            portfolio_id=portfolio_id,
            match_kind=kind,
            match_id="TEMP",  # Temporary placeholder
            reason=reason,
            created_by=actor_id,
            created_at=datetime.utcnow(),
            Modified_by=actor_id, # User Request: Populate Modified details in Trail
            Modified_at=datetime.utcnow(),
            Action="AUTO_MATCH"
        )
        self.db.add(trail)
        self.db.flush()  # Get trail.id
        
        # Generate Match ID using trail.id: PMSBNK + trail.id
        match_id_str = f"PMSBNK{trail.id}"
        
        # Update both match and trail with the generated match_id
        match.match_id = match_id_str
        trail.match_id = match_id_str

    def _create_finding(self, batch_id, side, entry_id, kind, reason, portfolio_id=None, actor_id="SYSTEM"):
        # Create Finding
        finding = BB_recon_findings(
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
        self.db.flush() # Get finding.id after insert

        # Create Trail
        from ..models import BB_recon_findings_trail
        trail = BB_recon_findings_trail(
            BB_recon_finding_ID=finding.id,
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
        
        # Sync finding from latest trail (ensures finding reflects trail state)
        self._sync_finding_from_trail(finding.id)
    
    def _sync_finding_from_trail(self, finding_id):
        """
        Synchronizes BB_recon_findings with the latest trail entry.
        This ensures the findings table always reflects the most recent state.
        """
        from ..models import BB_recon_findings_trail
        latest_trail = self.db.query(BB_recon_findings_trail).filter(
            BB_recon_findings_trail.BB_recon_finding_ID == finding_id
        ).order_by(BB_recon_findings_trail.id.desc()).first()
        
        if not latest_trail:
            return
        
        finding = self.db.query(BB_recon_findings).filter(
            BB_recon_findings.id == finding_id
        ).first()
        
        if finding:
            finding.finding_type = latest_trail.finding_type
            finding.finding_reason = latest_trail.finding_reason
            finding.Modified_by = latest_trail.Modified_by
            finding.Modified_at = latest_trail.Modified_at
            finding.portfolio_id = latest_trail.portfolio_id

