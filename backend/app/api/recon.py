from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.engine.core import ReconEngine
from app.models import BB_recon_batches, BB_recon_matches, BB_recon_findings, BatchStatus, BB_staging_bank_entries, BB_staging_broker_entries, MatchKind, SourceEnum, FindingType, FindingSide, BB_recon_matches_trail, BB_recon_findings_trail, AuditLog, BB_Recon_Files, ProcessingStatus
from pydantic import BaseModel
from app.core.security import get_api_key, Actor
import uuid
import logging
import asyncio
from datetime import datetime
from typing import List, Optional

router = APIRouter()

class RunReconRequest(BaseModel):
    broker_file_id: int
    bank_file_id: int
    tolerance_amount: Optional[float] = 0.0
    date_window_days: Optional[int] = 0

def _sync_finding_from_latest_trail(db: Session, finding_id: int):
    """
    Synchronizes BB_recon_findings with the latest trail entry.
    This ensures the findings table always reflects the most recent state.
    """
    latest_trail = db.query(BB_recon_findings_trail).filter(
        BB_recon_findings_trail.BB_recon_finding_ID == finding_id
    ).order_by(BB_recon_findings_trail.id.desc()).first()
    
    if not latest_trail:
        return
    
    finding = db.query(BB_recon_findings).filter(
        BB_recon_findings.id == finding_id
    ).first()
    
    if finding:
        finding.finding_type = latest_trail.finding_type
        finding.finding_reason = latest_trail.finding_reason
        finding.Modified_by = latest_trail.Modified_by
        finding.Modified_at = latest_trail.Modified_at
        finding.portfolio_id = latest_trail.portfolio_id

def _build_recon_response(batch_id: int, db: Session):
    # Fetch Matches (Filtered by Trail)
    # Logic: Get all matches where the latest action in Trail is NOT 'BREAK' or 'DISSOLVE'
    # Simplified Logic: Get all matches from BB_recon_matches that do NOT have a 'BREAK' or 'DISSOLVE' entry in Trail?
    # No, because a match could be broken and then re-matched (new ID).
    # But for a specific Match ID (Proof of Truth), if it has a BREAK event, it is invalid.
    
    # 1. Get List of Invalid Match IDs (those where LATEST action is BREAK or DISSOLVE)
    subquery = db.query(
        BB_recon_matches_trail.BB_recon_match_ID,
        BB_recon_matches_trail.Action,
        func.row_number().over(
            partition_by=BB_recon_matches_trail.BB_recon_match_ID,
            order_by=BB_recon_matches_trail.id.desc()
        ).label("rn")
    ).filter(BB_recon_matches_trail.batch_id == batch_id).subquery()
    
    invalid_match_rows = db.query(subquery.c.BB_recon_match_ID).filter(
        subquery.c.rn == 1,
        subquery.c.Action.in_(["BREAK", "DISSOLVE"])
    )

    # 1b. Get List of Invalid Finding IDs (those where LATEST action is MATCHED or RESOLVED)
    subquery_f = db.query(
        BB_recon_findings_trail.BB_recon_finding_ID,
        BB_recon_findings_trail.Action,
        func.row_number().over(
            partition_by=BB_recon_findings_trail.BB_recon_finding_ID,
            order_by=BB_recon_findings_trail.id.desc()
        ).label("rn")
    ).filter(BB_recon_findings_trail.batch_id == batch_id).subquery()
    
    resolved_finding_rows = db.query(subquery_f.c.BB_recon_finding_ID).filter(
        subquery_f.c.rn == 1,
        subquery_f.c.Action.in_(["MATCHED_MANUAL", "MATCHED_AUTO", "RESOLVED"])
    )

    # 2. Fetch Matches that are NOT in the invalid list
    matches = db.query(BB_recon_matches).filter(
        BB_recon_matches.batch_id == batch_id,
        BB_recon_matches.id.notin_(invalid_match_rows)
    ).all()

    # Fetch Findings
    # Fetch Findings (Filtered)
    findings = db.query(BB_recon_findings).filter(
        BB_recon_findings.batch_id == batch_id,
        BB_recon_findings.id.notin_(resolved_finding_rows)
    ).all()
    
    # Fetch original entries to hydrate data
    batch = db.query(BB_recon_batches).filter(BB_recon_batches.id == batch_id).first()
    if not batch: return None
        
    bank_file = batch.bank_file
    broker_file = batch.broker_file
    
    broker_entries_list = db.query(BB_staging_broker_entries).filter(BB_staging_broker_entries.file_id == broker_file.id).all()
    bank_entries_list = db.query(BB_staging_bank_entries).filter(BB_staging_bank_entries.file_id == bank_file.id).all()

    logger = logging.getLogger(__name__)
    logger.info(f"DEBUG: Batch {batch.id} | BankFile {bank_file.id} | BrokerFile {broker_file.id}")
    logger.info(f"DEBUG: Bank Records: {len(bank_entries_list)} | Broker Records: {len(broker_entries_list)}")
    logger.info(f"DEBUG: Bank IDs: {[r.id for r in bank_entries_list]}")

    broker_entries = {e.id: e for e in broker_entries_list}
    bank_entries = {e.id: e for e in bank_entries_list}

    # Build Response Lists
    res_broker = []
    res_bank = []
    
    # 3. Fetch Reasons from Trail (User Request)
    # Match Reasons
    match_reasons = {}
    match_trail_query = db.query(
        BB_recon_matches_trail.BB_recon_match_ID,
        BB_recon_matches_trail.reason
    ).filter(
        BB_recon_matches_trail.batch_id == batch_id
    ).order_by(BB_recon_matches_trail.id.desc())
    
    # We only want the LATEST reason for each match
    # A simple way is to fetch everything and let the dictionary overwrite with the latest if we iterate in order?
    # No, order_by desc means first one found is latest.
    
    match_trails = match_trail_query.all()
    for t in match_trails:
        if t.BB_recon_match_ID not in match_reasons:
             match_reasons[t.BB_recon_match_ID] = t.reason

    # Finding Reasons
    finding_reasons = {}
    finding_trail_query = db.query(
        BB_recon_findings_trail.BB_recon_finding_ID,
        BB_recon_findings_trail.finding_reason
    ).filter(
        BB_recon_findings_trail.batch_id == batch_id
    ).order_by(BB_recon_findings_trail.id.desc())
    
    finding_trails = finding_trail_query.all()
    for t in finding_trails:
        if t.BB_recon_finding_ID not in finding_reasons:
             finding_reasons[t.BB_recon_finding_ID] = t.finding_reason

    # Helper to format entry
    def fmt_entry(e, status, match_id="", reason="", match_kind=None, canonical_ref=None, db_match_id=None, db_finding_id=None):
        amt = float(e.amount_signed) if e.amount_signed is not None else 0.0
        
        # Override reason from trail if available
        final_reason = reason
        if db_match_id and db_match_id in match_reasons and match_reasons[db_match_id]:
             final_reason = match_reasons[db_match_id]
        elif db_finding_id and db_finding_id in finding_reasons and finding_reasons[db_finding_id]:
             final_reason = finding_reasons[db_finding_id]
             
        return {
            "id": str(e.id),
            "Date": e.value_date.isoformat() if e.value_date else None,
            "PortfolioID": e.portfolio_id,
            "Reference": e.reference_no,
            "Description": e.type_raw,
            "Debit": abs(amt) if amt < 0 else 0.0,
            "Credit": amt if amt > 0 else 0.0,
            "match_status": status, # MATCHED, UNMATCHED
            "match_kind": match_kind, # AUTO, MANUAL
            "match_id": match_id,
            "reason": final_reason,
            "canonical_reference": canonical_ref, # New Field
            "validation_error": e.validation_error
        }

    # Process Matches
    matched_broker_ids = set()
    matched_bank_ids = set()
    
    for m in matches:
        kind = m.match_kind.value if m.match_kind else "AUTO"
        reason_text = m.reason or "Auto Match"
        can_ref = m.canonical_reference
        
        if m.broker_entry_id in broker_entries:
            res_broker.append(fmt_entry(broker_entries[m.broker_entry_id], "MATCHED", m.match_id, reason_text, kind, can_ref, db_match_id=m.id))
            matched_broker_ids.add(m.broker_entry_id)
        if m.bank_entry_id in bank_entries:
            res_bank.append(fmt_entry(bank_entries[m.bank_entry_id], "MATCHED", m.match_id, reason_text, kind, can_ref, db_match_id=m.id))
            matched_bank_ids.add(m.bank_entry_id)
            
    # Process Findings (Unmatched / Exceptions)
    for f in findings:
        side_str = f.side.name if hasattr(f.side, 'name') else str(f.side)
        
        if side_str == "BROKER" and f.entry_id in broker_entries:
            if f.entry_id not in matched_broker_ids:
                status = "EXCEPTION" if f.finding_type.name == "EXCEPTION" else "UNMATCHED"
                res_broker.append(fmt_entry(broker_entries[f.entry_id], status, "", f.finding_reason, db_finding_id=f.id))
                matched_broker_ids.add(f.entry_id)
        elif side_str == "BANK" and f.entry_id in bank_entries:
            if f.entry_id not in matched_bank_ids:
                status = "EXCEPTION" if f.finding_type.name == "EXCEPTION" else "UNMATCHED"
                res_bank.append(fmt_entry(bank_entries[f.entry_id], status, "", f.finding_reason, db_finding_id=f.id))
                matched_bank_ids.add(f.entry_id)

    # Summary Stats Calculation
    unmatched_br = [x for x in res_broker if x['match_status'] == 'UNMATCHED']
    unmatched_bk = [x for x in res_bank if x['match_status'] == 'UNMATCHED']
    
    exception_br = [x for x in res_broker if x['match_status'] == 'EXCEPTION']
    exception_bk = [x for x in res_bank if x['match_status'] == 'EXCEPTION']
    
    def match_lists(list_a, list_b):
        # Matches items between two lists based on Ref or Date+Amt.
        pool_b_ref = {}
        pool_b_prop = {}
        for i, item in enumerate(list_b):
            ref = (item['Reference'] or "").strip()
            if ref and ref != '---':
                if ref not in pool_b_ref: pool_b_ref[ref] = []
                pool_b_ref[ref].append(i)
            
            amt = abs(item['Credit'] - item['Debit'])
            date = item['Date']
            key = (date, amt)
            if key not in pool_b_prop: pool_b_prop[key] = []
            pool_b_prop[key].append(i)
        
        matched_indices_b = set()
        matched_indices_a = set()
        pairs = 0
        
        for i, item in enumerate(list_a):
            ref = (item['Reference'] or "").strip()
            if ref and ref != '---' and ref in pool_b_ref:
                for idx in pool_b_ref[ref]:
                    if idx not in matched_indices_b:
                        matched_indices_b.add(idx)
                        matched_indices_a.add(i)
                        pairs += 1
                        break
            
            if i not in matched_indices_a:
                amt = abs(item['Credit'] - item['Debit'])
                date = item['Date']
                key = (date, amt)
                if key in pool_b_prop:
                    for idx in pool_b_prop[key]:
                        if idx not in matched_indices_b:
                            matched_indices_b.add(idx)
                            matched_indices_a.add(i)
                            pairs += 1
                            break
        
        rem_a = [item for i, item in enumerate(list_a) if i not in matched_indices_a]
        rem_b = [item for i, item in enumerate(list_b) if i not in matched_indices_b]
        return pairs, rem_a, rem_b

    # Group Exceptions
    ee_pairs, rem_ex_bk, rem_ex_br = match_lists(exception_bk, exception_br)
    eu_pairs, rem_ex_bk, rem_un_br = match_lists(rem_ex_bk, unmatched_br)
    ue_pairs, rem_un_bk, rem_ex_br = match_lists(unmatched_bk, rem_ex_br)
    total_exception_tasks = ee_pairs + eu_pairs + ue_pairs + len(rem_ex_bk) + len(rem_ex_br)
    
    # Group Unmatched
    uu_pairs, rem_un_bk_final, rem_un_br_final = match_lists(rem_un_bk, rem_un_br)
    total_unmatched_tasks = uu_pairs + len(rem_un_bk_final) + len(rem_un_br_final)

    auto_count = sum(1 for m in matches if m.match_kind == MatchKind.AUTO)
    manual_count = sum(1 for m in matches if m.match_kind == MatchKind.MANUAL)

    summary = {
        "total_matches": len(matches),
        "auto_match_count": auto_count,
        "manual_match_count": manual_count,
        "unmatched_count": total_unmatched_tasks,
        "exception_count": total_exception_tasks
    }

    return {
        "message": "Reconciliation Completed", 
        "batch_id": batch_id,
        "bank_file_id": bank_file.id,
        "broker_file_id": broker_file.id,
        "bank_records": res_bank,
        "broker_records": res_broker,
        "summary": summary
    }

@router.post("/recon/run")
async def run_reconciliation(
    req: RunReconRequest, 
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key)
):
    """
    Triggers separate Recon Batch and returns aggregated results for the frontend to render.
    Waits for file processing to complete before running the engine.
    """
    logger = logging.getLogger(__name__)
    
    # --- Wait for both files to finish background processing ---
    max_wait_seconds = 60
    poll_interval = 1.0  # seconds
    elapsed = 0
    
    while elapsed < max_wait_seconds:
        # Refresh session to see background task commits
        db.expire_all()
        
        broker_file = db.query(BB_Recon_Files).filter(BB_Recon_Files.id == req.broker_file_id).first()
        bank_file = db.query(BB_Recon_Files).filter(BB_Recon_Files.id == req.bank_file_id).first()
        
        if not broker_file:
            raise HTTPException(status_code=404, detail=f"Broker file {req.broker_file_id} not found")
        if not bank_file:
            raise HTTPException(status_code=404, detail=f"Bank file {req.bank_file_id} not found")
        
        broker_status = broker_file.processing_status
        bank_status = bank_file.processing_status
        
        logger.info(f"BB RECON: Waiting for files - Broker file {req.broker_file_id}: {broker_status}, Bank file {req.bank_file_id}: {bank_status}")
        
        # Check for failures
        if broker_status == ProcessingStatus.FAILED:
            raise HTTPException(status_code=400, detail=f"Broker file processing failed: {broker_file.processing_error}")
        if bank_status == ProcessingStatus.FAILED:
            raise HTTPException(status_code=400, detail=f"Bank file processing failed: {bank_file.processing_error}")
        if broker_status == ProcessingStatus.INFECTED:
            raise HTTPException(status_code=400, detail="Broker file is infected")
        if bank_status == ProcessingStatus.INFECTED:
            raise HTTPException(status_code=400, detail="Bank file is infected")
        
        # Both completed?
        if broker_status == ProcessingStatus.COMPLETED and bank_status == ProcessingStatus.COMPLETED:
            logger.info(f"BB RECON: Both files ready. Broker entries: {broker_file.transaction_count}, Bank entries: {bank_file.transaction_count}")
            break
        
        # Still processing - wait and retry
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    else:
        # Timed out
        raise HTTPException(
            status_code=408,
            detail=f"File processing timed out after {max_wait_seconds}s. Broker status: {broker_status}, Bank status: {bank_status}. Please try again."
        )
    
    # --- Now run the engine ---
    engine = ReconEngine(db)
    try:
        # 1. Run Engine
        batch_id = engine.run_batch(
            req.broker_file_id, 
            req.bank_file_id, 
            actor.name or actor.id,
            tolerance_amount=req.tolerance_amount,
            date_window_days=req.date_window_days
        )
        
        # 2. Fetch Results - Return ALL batches combined (not just current batch)
        # This ensures the frontend shows new data along with old data
        result = _build_all_batches_response(db)

        # Audit Log
        log = AuditLog(
            entity="ReconBatch",
            entity_id=str(batch_id),
            action="AUTO_MATCH_RUN",
            actor=actor.name or actor.id,
            payload={
                "summary": result.get("summary")
            }
        )
        db.add(log)
        db.commit()

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recon Error: {str(e)}")

def _build_all_batches_response(db: Session):
    """
    Build response combining data from ALL batches, with newest first.
    Applies same filtering logic as _build_recon_response for each batch.
    """
    # Fetch all batches ordered by ID desc (newest first)
    all_batches = db.query(BB_recon_batches).order_by(BB_recon_batches.id.desc()).all()
    
    if not all_batches:
        return {"message": "No reconciliation history found", "summary": None}
    
    combined_bank_records = []
    combined_broker_records = []
    
    # Aggregated summary counters
    total_matches = 0
    auto_match_count = 0
    manual_match_count = 0
    unmatched_count = 0
    exception_count = 0
    
    # Process each batch (newest first)
    for batch in all_batches:
        batch_data = _build_recon_response(batch.id, db)
        
        if batch_data and batch_data.get("summary"):
            # Extend combined records
            combined_bank_records.extend(batch_data.get("bank_records", []))
            combined_broker_records.extend(batch_data.get("broker_records", []))
            
            # Aggregate summary
            summary = batch_data.get("summary", {})
            total_matches += summary.get("total_matches", 0)
            auto_match_count += summary.get("auto_match_count", 0)
            manual_match_count += summary.get("manual_match_count", 0)
            unmatched_count += summary.get("unmatched_count", 0)
            exception_count += summary.get("exception_count", 0)
    
    # Use latest batch info for batch_id and file_ids
    latest_batch = all_batches[0]
    
    combined_summary = {
        "total_matches": total_matches,
        "auto_match_count": auto_match_count,
        "manual_match_count": manual_match_count,
        "unmatched_count": unmatched_count,
        "exception_count": exception_count
    }
    
    return {
        "message": "All batches combined",
        "batch_id": latest_batch.id,
        "bank_file_id": latest_batch.bank_file.id if latest_batch.bank_file else None,
        "broker_file_id": latest_batch.broker_file.id if latest_batch.broker_file else None,
        "bank_records": combined_bank_records,
        "broker_records": combined_broker_records,
        "summary": combined_summary
    }


@router.get("/recon/latest")
async def get_latest_recon(
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key)
):
    """
    Fetch results from ALL batches, combined, with newest first.
    """
    return _build_all_batches_response(db)

@router.get("/recon/status/{batch_id}")
async def get_recon_status(
    batch_id: int, 
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key)
):
    """
    Get status and high-level stats of a batch.
    """
    batch = db.query(BB_recon_batches).filter(BB_recon_batches.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
        
    return {
        "id": batch.id,
        "status": batch.status,
        "started_at": batch.started_at,
        "completed_at": batch.completed_at
    }

class ManualMatchRequest(BaseModel):
    batch_id: int
    bank_entry_ids: list[int]
    broker_entry_ids: list[int]
    note: str  # Now required
    update_bank_ref: str = None
    update_broker_ref: str = None
    canonical_reference: str = None
    manual_components: list[dict] = []  # [{"ref": str, "amount": float}] for manually-added rows
    parent_side: str = "auto"  # "bank" | "broker" | "auto" — which side is the ONE in a split

@router.post("/recon/manual-match")
async def manual_match(
    req: ManualMatchRequest,
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key)
):
    """
    Manually link Broker Entries and Bank Entries.
    Supports One-to-One, One-to-Many, and Many-to-One.
    Auto-splits the 'One' side to match the 'Many' side.
    """
    batch = db.query(BB_recon_batches).filter(BB_recon_batches.id == req.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    broker_entries = db.query(BB_staging_broker_entries).filter(BB_staging_broker_entries.id.in_(req.broker_entry_ids)).all()
    bank_entries = db.query(BB_staging_bank_entries).filter(BB_staging_bank_entries.id.in_(req.bank_entry_ids)).all()

    if len(broker_entries) != len(req.broker_entry_ids) or len(bank_entries) != len(req.bank_entry_ids):
        raise HTTPException(status_code=404, detail="One or more entries not found")

    if len(broker_entries) > 1 and len(bank_entries) > 1:
        raise HTTPException(status_code=400, detail="Many-to-Many matching is not supported. Please select one entry on at least one side.")
       
    if len(broker_entries) == 0 or len(bank_entries) == 0:
         raise HTTPException(status_code=400, detail="Must select at least one entry from both sides.")
    
    # Validate that note is provided
    if not req.note or not req.note.strip():
        raise HTTPException(status_code=400, detail="Reason/Note is required for manual match.")

    # Check for ANY existing match involving these entries (Active or Inactive)
    existing_match = db.query(BB_recon_matches).filter(
        BB_recon_matches.batch_id == batch.id,
        (BB_recon_matches.broker_entry_id.in_(req.broker_entry_ids)) |
        (BB_recon_matches.bank_entry_id.in_(req.bank_entry_ids))
    ).first()

    if existing_match:
        # Check status from Trail
        latest_trail = db.query(BB_recon_matches_trail).filter(
            BB_recon_matches_trail.BB_recon_match_ID == existing_match.id
        ).order_by(BB_recon_matches_trail.id.desc()).first()
        
        is_active = True
        if latest_trail and latest_trail.Action in ["BREAK", "DISSOLVE"]:
            is_active = False

        if is_active:
            raise HTTPException(
                status_code=400,
                detail=f"One or more entries are already matched (Match ID: {existing_match.match_id}). Unmatch them first if needed."
            )
        # If Inactive, we will attempt to Reuse it (only for 1-1 case, handled below)

    # Get batch tolerances
    tolerance_amount = batch.tolerance_amount if hasattr(batch, 'tolerance_amount') and batch.tolerance_amount is not None else 50.0
    date_window_days = batch.date_window_days if hasattr(batch, 'date_window_days') and batch.date_window_days is not None else 2
    
    # Sum amounts of real DB entries
    total_bank = sum(abs(float(e.amount_signed)) for e in bank_entries)
    total_broker = sum(abs(float(e.amount_signed)) for e in broker_entries)
    
    # Include manual components in the appropriate side total.
    # parent_side tells us which is the ONE side; manual components go on the MANY side.
    # If parent_side is "auto", fall back to whichever has MORE real entries.
    manual_total = sum(abs(float(mc.get('amount', 0))) for mc in req.manual_components)
    
    if len(req.manual_components) > 0:
        # Determine which side is the parent (the ONE)
        if req.parent_side == "bank":
            # bank is ONE, broker is MANY → manual adds to broker
            total_broker += manual_total
        elif req.parent_side == "broker":
            # broker is ONE, bank is MANY → manual adds to bank
            total_bank += manual_total
        else:
            # auto: add to whichever side has more entries (or broker if equal)
            if len(broker_entries) >= len(bank_entries):
                total_broker += manual_total
            else:
                total_bank += manual_total

    if abs(total_bank - total_broker) > tolerance_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Amount Mismatch: Bank Total ({total_bank}) != Broker Total ({total_broker}). Difference: {abs(total_bank - total_broker)}. Tolerance: {tolerance_amount}"
        )
    
    # Determine effective split routing when manual_components present
    # If parent_side forces 1-to-many routing even when real entries are 1-to-1
    effective_bank_is_parent = (
        req.parent_side == "bank" or 
        (req.parent_side == "auto" and len(bank_entries) == 1 and len(broker_entries) > 1)
    )
    effective_broker_is_parent = (
        req.parent_side == "broker" or 
        (req.parent_side == "auto" and len(broker_entries) == 1 and len(bank_entries) > 1)
    )
        
    # STRICT VALIDATION (User Request)
    all_entries = bank_entries + broker_entries
    
    # STRICT VALIDATION (User Request)
    all_entries = bank_entries + broker_entries
    
    # 1. Validate Portfolio ID
    distinct_portfolios = {e.portfolio_id for e in all_entries}
    if len(distinct_portfolios) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Portfolio Mismatch: Selected entries belong to different Portfolios: {distinct_portfolios}"
        )
    
    common_portfolio_id = list(distinct_portfolios)[0] if distinct_portfolios else None
        
    # 2. Validate Value Date (with tolerance)
    from datetime import timedelta
    
    # Get all unique dates
    all_dates = [e.value_date for e in all_entries if e.value_date]
    if not all_dates:
        raise HTTPException(status_code=400, detail="All entries must have a value date.")
    
    # Check if all dates are within the tolerance window
    min_date = min(all_dates)
    max_date = max(all_dates)
    date_diff = (max_date - min_date).days
    
    if date_diff > date_window_days:
        raise HTTPException(
            status_code=400,
            detail=f"Date Mismatch: Selected entries have dates spanning {date_diff} days (from {min_date} to {max_date}). Tolerance: {date_window_days} days"
        )
        
    # LOGIC FOR SPLIT MATCHING
    if (effective_bank_is_parent and len(req.manual_components) > 0) or (len(bank_entries) == 1 and len(broker_entries) > 1):
        # Bank is parent, broker entries are many (real + manual)
        parent_bank = bank_entries[0]
        new_matches = []
        for br in broker_entries:
            original_sign = 1 if float(parent_bank.amount_signed) >= 0 else -1
            target_amt = abs(float(br.amount_signed)) * original_sign
            split_part = BB_staging_bank_entries(
                file_id=parent_bank.file_id,
                value_date=parent_bank.value_date,
                portfolio_id=parent_bank.portfolio_id, # Copy Portfolio
                reference_no=req.update_bank_ref or parent_bank.reference_no, 
                amount_signed=target_amt,
                type_raw=f"{parent_bank.type_raw} (Split)",
                validation_error=None 
            )
            db.add(split_part)
            db.flush() 
            
            # Create match with temporary match_id
            match = BB_recon_matches(
                batch_id=batch.id,
                broker_entry_id=br.id,
                bank_entry_id=split_part.id,
                portfolio_id=parent_bank.portfolio_id, # FIX: Add Portfolio ID
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",  # Temporary placeholder
                canonical_reference=req.canonical_reference or f"MAN-LINK-{batch.id}",
                reason=req.note or "Manual Split Match",
                created_by=actor.name or actor.id # FIX: Use Name
            )
            db.add(match)
            db.flush()
            
            # Trail
            trail = BB_recon_matches_trail(
                BB_recon_match_ID=match.id,
                batch_id=batch.id,
                broker_entry_id=br.id,
                bank_entry_id=split_part.id,
                portfolio_id=parent_bank.portfolio_id, # FIX: Add Portfolio ID
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",  # Temporary placeholder
                reason=match.reason,
                created_by=actor.name or actor.id, # FIX: Use Name
                created_at=datetime.utcnow(),
                Modified_by=actor.name or actor.id, # FIX: Populate Modified for Trail
                Modified_at=datetime.utcnow(),
                Action="MANUAL_SPLIT"
            )
            db.add(trail)
            db.flush()  # Get trail.id
            
            # Generate Match ID using trail.id: PMSBNK + trail.id
            match_id_str = f"PMSBNK{trail.id}"
            
            # Update both match and trail with the generated match_id
            match.match_id = match_id_str
            trail.match_id = match_id_str
            new_matches.append(match)
        
        # Also create DB entries + matches for each manual component
        for mc in req.manual_components:
            mc_amt = float(mc.get('amount', 0))
            mc_ref = mc.get('ref', req.update_bank_ref or parent_bank.reference_no)
            original_sign = 1 if float(parent_bank.amount_signed) >= 0 else -1
            target_amt = abs(mc_amt) * original_sign
            
            mc_part = BB_staging_broker_entries(
                file_id=parent_bank.file_id,  # use bank file as placeholder
                value_date=parent_bank.value_date,
                portfolio_id=parent_bank.portfolio_id,
                reference_no=mc_ref,
                amount_signed=target_amt,
                type_raw=f"{parent_bank.type_raw} (Manual Split)",
                validation_error=None
            )
            db.add(mc_part)
            db.flush()
            
            mc_split = BB_staging_bank_entries(
                file_id=parent_bank.file_id,
                value_date=parent_bank.value_date,
                portfolio_id=parent_bank.portfolio_id,
                reference_no=mc_ref,
                amount_signed=target_amt,
                type_raw=f"{parent_bank.type_raw} (Manual Split)",
                validation_error=None
            )
            db.add(mc_split)
            db.flush()
            
            mc_match = BB_recon_matches(
                batch_id=batch.id,
                broker_entry_id=mc_part.id,
                bank_entry_id=mc_split.id,
                portfolio_id=parent_bank.portfolio_id,
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",
                canonical_reference=req.canonical_reference or f"MAN-SPLIT-{batch.id}",
                reason=req.note or "Manual Split Match",
                created_by=actor.name or actor.id
            )
            db.add(mc_match)
            db.flush()
            mc_trail = BB_recon_matches_trail(
                BB_recon_match_ID=mc_match.id,
                batch_id=batch.id,
                broker_entry_id=mc_part.id,
                bank_entry_id=mc_split.id,
                portfolio_id=parent_bank.portfolio_id,
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",
                reason=mc_match.reason,
                created_by=actor.name or actor.id,
                created_at=datetime.utcnow(),
                Modified_by=actor.name or actor.id,
                Modified_at=datetime.utcnow(),
                Action="MANUAL_SPLIT"
            )
            db.add(mc_trail)
            db.flush()
            mc_id_str = f"PMSBNK{mc_trail.id}"
            mc_match.match_id = mc_id_str
            mc_trail.match_id = mc_id_str
            new_matches.append(mc_match)
        
        db.delete(parent_bank)
        
    elif (effective_broker_is_parent and len(req.manual_components) > 0) or (len(bank_entries) > 1 and len(broker_entries) == 1):
        # Broker is parent, bank entries are many (real + manual)
        parent_broker = broker_entries[0]
        new_matches = []
        for bk in bank_entries:
            original_sign = 1 if float(parent_broker.amount_signed) >= 0 else -1
            target_amt = abs(float(bk.amount_signed)) * original_sign
            split_part = BB_staging_broker_entries(
                file_id=parent_broker.file_id,
                value_date=parent_broker.value_date,
                portfolio_id=parent_broker.portfolio_id, # Copy Portfolio
                reference_no=req.update_broker_ref or parent_broker.reference_no,
                amount_signed=target_amt,
                type_raw=f"{parent_broker.type_raw} (Split)",
                validation_error=None
            )
            db.add(split_part)
            db.flush()
            
            # Create match with temporary match_id
            match = BB_recon_matches(
                batch_id=batch.id,
                broker_entry_id=split_part.id,
                bank_entry_id=bk.id,
                portfolio_id=parent_broker.portfolio_id, # FIX: Add Portfolio ID
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",  # Temporary placeholder
                canonical_reference=req.canonical_reference or f"MAN-LINK-{batch.id}",
                reason=req.note or "Manual Split Match",
                created_by=actor.name or actor.id # FIX: Use Name
            )
            db.add(match)
            db.flush()

            # Trail
            trail = BB_recon_matches_trail(
                BB_recon_match_ID=match.id,
                batch_id=batch.id,
                broker_entry_id=split_part.id,
                bank_entry_id=bk.id,
                portfolio_id=parent_broker.portfolio_id, # FIX: Add Portfolio ID
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",  # Temporary placeholder
                reason=match.reason,
                created_by=actor.name or actor.id, # FIX: Use Name
                created_at=datetime.utcnow(),
                Modified_by=actor.name or actor.id, # FIX: Populate Modified for Trail
                Modified_at=datetime.utcnow(),
                Action="MANUAL_SPLIT"
            )
            db.add(trail)
            db.flush()  # Get trail.id
            
            # Generate Match ID using trail.id: PMSBNK + trail.id
            match_id_str = f"PMSBNK{trail.id}"
            
            # Update both match and trail with the generated match_id
            match.match_id = match_id_str
            trail.match_id = match_id_str
            new_matches.append(match)
        
        # Also create DB entries + matches for each manual component
        for mc in req.manual_components:
            mc_amt = float(mc.get('amount', 0))
            mc_ref = mc.get('ref', req.update_broker_ref or parent_broker.reference_no)
            original_sign = 1 if float(parent_broker.amount_signed) >= 0 else -1
            target_amt = abs(mc_amt) * original_sign
            
            mc_bank_part = BB_staging_bank_entries(
                file_id=parent_broker.file_id,
                value_date=parent_broker.value_date,
                portfolio_id=parent_broker.portfolio_id,
                reference_no=mc_ref,
                amount_signed=target_amt,
                type_raw=f"{parent_broker.type_raw} (Manual Split)",
                validation_error=None
            )
            db.add(mc_bank_part)
            db.flush()
            
            mc_broker_part = BB_staging_broker_entries(
                file_id=parent_broker.file_id,
                value_date=parent_broker.value_date,
                portfolio_id=parent_broker.portfolio_id,
                reference_no=mc_ref,
                amount_signed=target_amt,
                type_raw=f"{parent_broker.type_raw} (Manual Split)",
                validation_error=None
            )
            db.add(mc_broker_part)
            db.flush()
            
            mc_match = BB_recon_matches(
                batch_id=batch.id,
                broker_entry_id=mc_broker_part.id,
                bank_entry_id=mc_bank_part.id,
                portfolio_id=parent_broker.portfolio_id,
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",
                canonical_reference=req.canonical_reference or f"MAN-SPLIT-{batch.id}",
                reason=req.note or "Manual Split Match",
                created_by=actor.name or actor.id
            )
            db.add(mc_match)
            db.flush()
            mc_trail = BB_recon_matches_trail(
                BB_recon_match_ID=mc_match.id,
                batch_id=batch.id,
                broker_entry_id=mc_broker_part.id,
                bank_entry_id=mc_bank_part.id,
                portfolio_id=parent_broker.portfolio_id,
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",
                reason=mc_match.reason,
                created_by=actor.name or actor.id,
                created_at=datetime.utcnow(),
                Modified_by=actor.name or actor.id,
                Modified_at=datetime.utcnow(),
                Action="MANUAL_SPLIT"
            )
            db.add(mc_trail)
            db.flush()
            mc_id_str = f"PMSBNK{mc_trail.id}"
            mc_match.match_id = mc_id_str
            mc_trail.match_id = mc_id_str
            new_matches.append(mc_match)
        
        db.delete(parent_broker)

    else:
        # 1-1 Match Case
        bk = bank_entries[0]
        br = broker_entries[0]
        
        # Check if we can reuse an existing inactive match for strict 1-1
        # reusing 'existing_match' from earlier if it matches this pair
        
        reused = False
        match = None
        
        if existing_match:
             # Ensure the existing match exactly pairs these two
             if existing_match.broker_entry_id == br.id and existing_match.bank_entry_id == bk.id:
                 match = existing_match
                 reused = True
        
        if reused and match:
            # Update Existing Match
            match.reason = req.note or f"Manual Link by {actor.name or actor.id}"
            # match.match_kind = MatchKind.MANUAL # Preserving original kind? 
            # User example showed AUTO in one case, but usually manual link implies MANUAL. 
            # I will set to MANUAL to be safe, unless it was already AUTO and we want to preserve?
            # User screenshot 3 showed "match_kind | AUTO". If I really want to mimic that...
            # But the user also said "manual link by user_name".
            # I'll update it to MANUAL as it is a manual action.
            # If the user specifically wants AUTO, they can ask.
            match.match_kind = MatchKind.MANUAL 
            
            match.Modified_by = actor.name or actor.id
            match.Modified_at = datetime.utcnow()
            if req.canonical_reference:
                match.canonical_reference = req.canonical_reference
            
            # Note: Do not add new BB_recon_matches, just flush
            new_matches = [match]
            db.flush()
            
            match_id_str = match.match_id
            
        else:
            # Create New Match
            if req.update_bank_ref: bk.reference_no = req.update_bank_ref
            if req.update_broker_ref: br.reference_no = req.update_broker_ref
            
            # Create match with temporary match_id
            match = BB_recon_matches(
                batch_id=batch.id,
                broker_entry_id=br.id,
                bank_entry_id=bk.id,
                portfolio_id=common_portfolio_id, # FIX: Add Portfolio ID
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",  # Temporary placeholder
                canonical_reference=req.canonical_reference or f"MAN-LINK-{batch.id}",
                reason=req.note or f"Manual Link by {actor.name or actor.id}",
                created_by=actor.name or actor.id # FIX: Use Name
            )
            db.add(match)
            db.flush()
            new_matches = [match]

        # Trail
        trail = BB_recon_matches_trail(
            BB_recon_match_ID=match.id,
            batch_id=batch.id,
            broker_entry_id=br.id,
            bank_entry_id=bk.id,
            portfolio_id=common_portfolio_id, # FIX: Add Portfolio ID
            match_kind=match.match_kind,
            match_id="TEMP",  # Temporary placeholder
            reason=match.reason,
            created_by=match.created_by,
            created_at=match.created_at,
            Modified_by=actor.name or actor.id, 
            Modified_at=datetime.utcnow(),
            Action="MANUAL_MATCH"
        )
        db.add(trail)
        db.flush()  # Get trail.id
        
        # Generate Match ID using trail.id: PMSBNK + trail.id
        match_id_str = f"PMSBNK{trail.id}"
        
        # Update both match and trail with the generated match_id
        match.match_id = match_id_str
        trail.match_id = match_id_str

    original_broker_ids = [e.id for e in broker_entries]
    original_bank_ids = [e.id for e in bank_entries]
    
    findings_to_update = db.query(BB_recon_findings).filter(
        BB_recon_findings.batch_id == batch.id,
        ((BB_recon_findings.side == FindingSide.BROKER) & (BB_recon_findings.entry_id.in_(original_broker_ids))) |
        ((BB_recon_findings.side == FindingSide.BANK) & (BB_recon_findings.entry_id.in_(original_bank_ids)))
    ).all()
    
    for f in findings_to_update:
        # Create Trail Entry
        trail_f = BB_recon_findings_trail(
            BB_recon_finding_ID=f.id,
            batch_id=batch.id,
            side=f.side,
            entry_id=f.entry_id,
            portfolio_id=f.portfolio_id,
            finding_type=f.finding_type,
            finding_reason=f"Matched Manually by {actor.name or actor.id}",
            created_at=f.created_at,
            created_by=f.created_by,
            Modified_by=actor.name or actor.id,
            Modified_at=datetime.utcnow(),
            Action="MATCHED_MANUAL"
        )
        db.add(trail_f)
        db.flush()
        
        # Sync finding from latest trail
        _sync_finding_from_latest_trail(db, f.id)

    # Determine Action Type for Audit Log
    action_log_type = "CREATE_MANUAL_MATCH_SPLIT"
    if len(bank_entries) == 1 and len(broker_entries) == 1:
        action_log_type = "CREATE_MANUAL_MATCH_LINK"

    # Audit Log
    from app.models import AuditLog
    # Audit Log
    from app.models import AuditLog
    
    for match in new_matches:
        log = AuditLog(
            entity="ReconMatch",
            entity_id=match.match_id,
            action=action_log_type,
            actor=actor.name or actor.id,
            payload={
                "batch_id": batch.id,
                "bank_ids": req.bank_entry_ids,
                "broker_ids": req.broker_entry_ids,
                "note": req.note,
                "match_count": len(new_matches)
            }
        )
        db.add(log)
    
    db.commit()
    return {"message": "Manual Match Successful", "match_count": len(new_matches)}


class DissolveMatchRequest(BaseModel):
    match_id: str
    batch_id: int

@router.post("/recon/dissolve-match")
async def dissolve_match(
    req: DissolveMatchRequest,
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key)
):
    """
    Dissolves ONLY Split Matches.
    """
    target_match = db.query(BB_recon_matches).filter(
        BB_recon_matches.batch_id == req.batch_id,
        BB_recon_matches.match_id == req.match_id
    ).first()

    if not target_match:
        raise HTTPException(status_code=404, detail="Match not found")

    is_split = target_match.canonical_reference and "MAN-SPLIT" in target_match.canonical_reference
    
    if not is_split:
        raise HTTPException(status_code=400, detail="Only Split Matches can be dissolved.")
        
    group_ref = target_match.canonical_reference
    group_matches = db.query(BB_recon_matches).filter(
        BB_recon_matches.batch_id == req.batch_id,
        BB_recon_matches.canonical_reference == group_ref
    ).all()
    
    if not group_matches:
        raise HTTPException(status_code=404, detail="Split Group not found")

    broker_ids = [m.broker_entry_id for m in group_matches]
    bank_ids = [m.bank_entry_id for m in group_matches]
    
    split_broker_entries = db.query(BB_staging_broker_entries).filter(BB_staging_broker_entries.id.in_(broker_ids)).all()
    split_bank_entries = db.query(BB_staging_bank_entries).filter(BB_staging_bank_entries.id.in_(bank_ids)).all()
    
    from decimal import Decimal
    logger = logging.getLogger(__name__)

    bank_is_split = any("(Split)" in (e.type_raw or "") for e in split_bank_entries)
    broker_is_split = any("(Split)" in (e.type_raw or "") for e in split_broker_entries)
    
    logger.info(f"Dissolving Split: BankSplit={bank_is_split}, BrokerSplit={broker_is_split}, GroupRef={group_ref}")

    try:
        # 1. Delete Matches FIRST
        # 1. Delete Matches and Trails (Hard Delete required to delete Staging Children)
        for m in group_matches:
            # Delete Trails referencing this match first (to avoid FK violation on Match delete/Child delete)
            db.query(BB_recon_matches_trail).filter(BB_recon_matches_trail.BB_recon_match_ID == m.id).delete()
            
            # Delete the Match
            db.delete(m)
        
        # 2. Restore Parent and Delete Children
        new_parent = None
        if bank_is_split:
            children = split_bank_entries
            if not children:
                 raise HTTPException(status_code=400, detail="No bank children found for split")
            
            first = children[0]
            total_amt = sum(Decimal(str(c.amount_signed)) for c in children)
            original_type = first.type_raw.replace(" (Split)", "").strip() if first.type_raw else "Unknown"
            
            new_parent = BB_staging_bank_entries(
                file_id=first.file_id,
                value_date=first.value_date,
                portfolio_id=first.portfolio_id,
                reference_no=first.reference_no,
                amount_signed=total_amt,
                type_raw=original_type,
                validation_error=None
            )
            db.add(new_parent)
            for child in children:
                db.delete(child)
                
        elif broker_is_split:
            children = split_broker_entries
            if not children:
                 raise HTTPException(status_code=400, detail="No broker children found for split")
            
            first = children[0]
            total_amt = sum(Decimal(str(c.amount_signed)) for c in children)
            original_type = first.type_raw.replace(" (Split)", "").strip() if first.type_raw else "Unknown"
            
            new_parent = BB_staging_broker_entries(
                file_id=first.file_id,
                value_date=first.value_date,
                portfolio_id=first.portfolio_id,
                reference_no=first.reference_no,
                amount_signed=total_amt,
                type_raw=original_type,
                validation_error=None
            )
            db.add(new_parent)
            for child in children:
                db.delete(child)
        
        db.flush()
        if new_parent and new_parent.id:
             side_enum = FindingSide.BANK if bank_is_split else FindingSide.BROKER
             
             # Create Finding for Restored Parent
             finding = BB_recon_findings(
                 batch_id=req.batch_id,
                 side=side_enum,
                 entry_id=new_parent.id,
                 portfolio_id=new_parent.portfolio_id,
                 finding_type=FindingType.UNMATCHED,
                 finding_reason="Restored from Dissolve",
                 created_at=datetime.utcnow(),
                 created_by=actor.name or actor.id,
                 Modified_by=actor.name or actor.id,
                 Modified_at=datetime.utcnow()
             )
             db.add(finding)
             db.flush()
             
             trail_f = BB_recon_findings_trail(
                BB_recon_finding_ID=finding.id,
                batch_id=req.batch_id,
                side=finding.side,
                entry_id=finding.entry_id,
                portfolio_id=finding.portfolio_id,
                finding_type=finding.finding_type,
                finding_reason=finding.finding_reason,
                created_at=finding.created_at,
                created_by=finding.created_by,
                Modified_by=finding.Modified_by,
                Modified_at=finding.Modified_at,
                Action="CREATED"
             )
             db.add(trail_f)
             db.flush()
             
             # Sync finding from latest trail
             _sync_finding_from_latest_trail(db, finding.id)
        
        # 3. Restore Visibility for the Non-Split Side
        # 3. Restore Visibility for the Non-Split Side
        if bank_is_split:
            for br in split_broker_entries:
                 f_existing = db.query(BB_recon_findings).filter(
                     BB_recon_findings.batch_id == req.batch_id,
                     BB_recon_findings.side == FindingSide.BROKER,
                     BB_recon_findings.entry_id == br.id
                 ).first()
                 
                 if f_existing:
                     # Revive
                     f_existing.Modified_by = actor.name or actor.id
                     f_existing.Modified_at = datetime.utcnow()
                     f_existing.finding_reason = "Unmatched via Dissolve"
                     
                     trail_revive = BB_recon_findings_trail(
                        BB_recon_finding_ID=f_existing.id,
                        batch_id=f_existing.batch_id,
                        side=f_existing.side,
                        entry_id=f_existing.entry_id,
                        portfolio_id=f_existing.portfolio_id,
                        finding_type=f_existing.finding_type,
                        finding_reason=f_existing.finding_reason,
                        created_at=f_existing.created_at,
                        created_by=f_existing.created_by,
                        Modified_by=actor.name or actor.id,
                        Modified_at=datetime.utcnow(),
                        Action="UNMATCHED_DISSOLVE"
                     )
                     db.add(trail_revive)
                     db.flush()
                     
                     # Sync finding from latest trail
                     _sync_finding_from_latest_trail(db, f_existing.id)
                 else:
                     # Create New
                     f_br = BB_recon_findings(
                         batch_id=req.batch_id,
                         side=FindingSide.BROKER, # Counterparty is Broker
                         entry_id=br.id,
                         portfolio_id=br.portfolio_id,
                         finding_type=FindingType.UNMATCHED,
                         finding_reason="Unmatched via Dissolve",
                         created_at=datetime.utcnow(),
                         created_by=actor.name or actor.id,
                         Modified_by=actor.name or actor.id,
                         Modified_at=datetime.utcnow()
                     )
                     db.add(f_br)
                     db.flush()
                     
                     trail_create = BB_recon_findings_trail(
                        BB_recon_finding_ID=f_br.id,
                        batch_id=f_br.batch_id,
                        side=f_br.side,
                        entry_id=f_br.entry_id,
                        portfolio_id=f_br.portfolio_id,
                        finding_type=f_br.finding_type,
                        finding_reason=f_br.finding_reason,
                        created_at=f_br.created_at,
                        created_by=f_br.created_by,
                        Modified_by=actor.name or actor.id,
                        Modified_at=datetime.utcnow(),
                        Action="CREATED"
                     )
                     db.add(trail_create)
                     db.flush()
                     
                     # Sync finding from latest trail
                     _sync_finding_from_latest_trail(db, f_br.id)

        elif broker_is_split:
            for bk in split_bank_entries:
                 f_existing = db.query(BB_recon_findings).filter(
                     BB_recon_findings.batch_id == req.batch_id,
                     BB_recon_findings.side == FindingSide.BANK,
                     BB_recon_findings.entry_id == bk.id
                 ).first()

                 if f_existing:
                     # Revive
                     f_existing.Modified_by = actor.name or actor.id
                     f_existing.Modified_at = datetime.utcnow()
                     f_existing.finding_reason = "Unmatched via Dissolve"
                     
                     trail_revive = BB_recon_findings_trail(
                        BB_recon_finding_ID=f_existing.id,
                        batch_id=f_existing.batch_id,
                        side=f_existing.side,
                        entry_id=f_existing.entry_id,
                        portfolio_id=f_existing.portfolio_id,
                        finding_type=f_existing.finding_type,
                        finding_reason=f_existing.finding_reason,
                        created_at=f_existing.created_at,
                        created_by=f_existing.created_by,
                        Modified_by=actor.name or actor.id,
                        Modified_at=datetime.utcnow(),
                        Action="UNMATCHED_DISSOLVE"
                     )
                     db.add(trail_revive)
                 else:
                     f_bk = BB_recon_findings(
                         batch_id=req.batch_id,
                         side=FindingSide.BANK, # Counterparty is Bank
                         entry_id=bk.id,
                         portfolio_id=bk.portfolio_id,
                         finding_type=FindingType.UNMATCHED,
                         finding_reason="Unmatched via Dissolve",
                         created_at=datetime.utcnow(),
                         created_by=actor.name or actor.id,
                         Modified_by=actor.name or actor.id,
                         Modified_at=datetime.utcnow()
                     )
                     db.add(f_bk)
                     db.flush()

                     trail_create = BB_recon_findings_trail(
                        BB_recon_finding_ID=f_bk.id,
                        batch_id=f_bk.batch_id,
                        side=f_bk.side,
                        entry_id=f_bk.entry_id,
                        portfolio_id=f_bk.portfolio_id,
                        finding_type=f_bk.finding_type,
                        finding_reason=f_bk.finding_reason,
                        created_at=f_bk.created_at,
                        created_by=f_bk.created_by,
                        Modified_by=actor.name or actor.id,
                        Modified_at=datetime.utcnow(),
                        Action="CREATED"
                     )
                     db.add(trail_create)
                     db.flush()
                     
                     # Sync finding from latest trail
                     _sync_finding_from_latest_trail(db, f_bk.id)

    except Exception as e:
        logger.error(f"Error restoring split parent: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to restore parent entry: {str(e)}")

    # Audit Log
    from app.models import AuditLog
    log = AuditLog(
        entity="ReconMatch",
        entity_id=req.match_id,
        action="DISSOLVE_MATCH",
        actor=actor.name or actor.id,
        payload={
            "batch_id": req.batch_id,
            "type": "SPLIT_UNDO",
            "group_ref": target_match.canonical_reference
        }
    )
    db.add(log)

    db.commit()
    return {"message": "Split Match Dissolved Successfully"}

class BreakMatchRequest(BaseModel):
    batch_id: int
    match_id: str
    reason: str  # Now required

@router.post("/recon/break-match")
async def break_match(
    req: BreakMatchRequest,
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key)
):
    """
    Breaks a match (Auto or Manual), returning the records to 'Unmatched' status.
    """
    # Validate that reason is provided
    if not req.reason or not req.reason.strip():
        raise HTTPException(status_code=400, detail="Reason is required to break a match.")
    
    target_match = db.query(BB_recon_matches).filter(
        BB_recon_matches.batch_id == req.batch_id,
        BB_recon_matches.match_id == req.match_id
    ).first()

    if not target_match:
        raise HTTPException(status_code=404, detail="Match not found")

    try:
        # 1. Capture IDs before deleting match
        broker_id = target_match.broker_entry_id
        bank_id = target_match.bank_entry_id
        
        # 2. Delete Match
        # 2. SOFT DELETE Match
        # db.delete(target_match) # REMOVED
        
        target_match.Modified_by = actor.name or actor.id # FIX: Use Name
        target_match.Modified_at = datetime.utcnow()
        target_match.reason = req.reason # Use user-provided reason
        
        trail = BB_recon_matches_trail(
            BB_recon_match_ID=target_match.id,
            batch_id=req.batch_id,
            broker_entry_id=broker_id,
            bank_entry_id=bank_id,
            portfolio_id=target_match.portfolio_id,
            match_kind=target_match.match_kind,
            match_id=target_match.match_id,
            reason=req.reason,  # Use user-provided reason
            created_by=target_match.created_by,
            created_at=target_match.created_at,
            Modified_by=actor.name or actor.id, # FIX: Use Name
            Modified_at=datetime.utcnow(),
            Action="BREAK"
        )
        db.add(trail)
        
        # 3. Create UNMATCHED findings (Revive or Create)
        
        # Helper to revive or create
        def revive_or_create_finding(side, entry_id, portfolio_id):
            f_existing = db.query(BB_recon_findings).filter(
                BB_recon_findings.batch_id == req.batch_id,
                BB_recon_findings.side == side,
                BB_recon_findings.entry_id == entry_id
            ).first()
            
            if f_existing:
                f_existing.Modified_by = actor.name or actor.id
                f_existing.Modified_at = datetime.utcnow()
                f_existing.finding_reason = "Match Broken by User"
                
                trail_revive = BB_recon_findings_trail(
                    BB_recon_finding_ID=f_existing.id,
                    batch_id=f_existing.batch_id,
                    side=f_existing.side,
                    entry_id=f_existing.entry_id,
                    portfolio_id=f_existing.portfolio_id,
                    finding_type=f_existing.finding_type,
                    finding_reason=f_existing.finding_reason,
                    created_at=f_existing.created_at,
                    created_by=f_existing.created_by,
                    Modified_by=actor.name or actor.id,
                    Modified_at=datetime.utcnow(),
                    Action="UNMATCHED_BREAK"
                )
                db.add(trail_revive)
                db.flush()
                
                # Sync finding from latest trail
                _sync_finding_from_latest_trail(db, f_existing.id)
            else:
                f_new = BB_recon_findings(
                     batch_id=req.batch_id,
                     side=side,
                     entry_id=entry_id,
                     portfolio_id=portfolio_id,
                     finding_type=FindingType.UNMATCHED,
                     finding_reason="Match Broken by User",
                     created_at=datetime.utcnow(),
                     created_by=actor.name or actor.id,
                     Modified_by=actor.name or actor.id,
                     Modified_at=datetime.utcnow()
                )
                db.add(f_new)
                db.flush()
                
                trail_create = BB_recon_findings_trail(
                    BB_recon_finding_ID=f_new.id,
                    batch_id=f_new.batch_id,
                    side=f_new.side,
                    entry_id=f_new.entry_id,
                    portfolio_id=f_new.portfolio_id,
                    finding_type=f_new.finding_type,
                    finding_reason=f_new.finding_reason,
                    created_at=f_new.created_at,
                    created_by=f_new.created_by,
                    Modified_by=actor.name or actor.id,
                    Modified_at=datetime.utcnow(),
                    Action="CREATED"
                )
                db.add(trail_create)
                db.flush()
                
                # Sync finding from latest trail
                _sync_finding_from_latest_trail(db, f_new.id)

        revive_or_create_finding(FindingSide.BANK, bank_id, target_match.portfolio_id)
        revive_or_create_finding(FindingSide.BROKER, broker_id, target_match.portfolio_id)

        # Audit Log
        from app.models import AuditLog
        log = AuditLog(
            entity="ReconMatch",
            entity_id=req.match_id,
            action="BREAK_MATCH",
            actor=actor.name or actor.id,
            payload={
                "batch_id": req.batch_id,
                "broker_entry_id": broker_id,
                "bank_entry_id": bank_id
            }
        )
        db.add(log)
        
        db.commit()
        return {"message": "Match Broken Successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to break match: {str(e)}")
