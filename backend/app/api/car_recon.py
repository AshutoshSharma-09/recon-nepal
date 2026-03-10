from fastapi import APIRouter, Depends, HTTPException, Security, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db, SessionLocal
from app.engine.car_core import CarReconEngine
from app.models import (
    CR_recon_batches, CR_recon_matches, CR_recon_findings, BatchStatus, 
    CR_staging_Cash_entries, CR_staging_Receivable_entries, 
    MatchKind, CR_SourceEnum, FindingType, FindingSide, 
    CR_recon_matches_trail, CR_recon_findings_trail, AuditLog,
    CR_Recon_Files, ProcessingStatus
)
from pydantic import BaseModel
from app.core.security import get_api_key, Actor
from app.core.upload import SecureUpload
from app.ingestion.parsers import CashArCsvParser
import logging
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import os

router = APIRouter()
logger = logging.getLogger(__name__)

# --- INGESTION ---

def process_car_file_async(file_id: int, file_path: str, source: CR_SourceEnum, actor_name: str):
    db = SessionLocal()
    source_str = "CASH" if source == CR_SourceEnum.CASH else "AR"
    parser = CashArCsvParser(source=source_str)
    
    try:
        recon_file = db.query(CR_Recon_Files).filter(CR_Recon_Files.id == file_id).first()
        if not recon_file: return

        recon_file.processing_status = ProcessingStatus.PROCESSING
        db.commit()

        entries = parser.parse(Path(file_path).read_bytes())
        
        if not entries:
            recon_file.processing_status = ProcessingStatus.FAILED
            recon_file.processing_error = "No valid transactions found"
            db.commit()
            return

        db_entries = []
        if source == CR_SourceEnum.CASH:
            model = CR_staging_Cash_entries
            for e in entries:
                db_entries.append({
                    'file_id': file_id,
                    'value_date': e['value_date'] or None,
                    'portfolio_id': e['portfolio_id'] or None,
                    'vch_id': e['vch_id'] or None,
                    'db_amount': e['amount'],          # None stored as NULL when missing
                    'transaction_name': e['transaction_name'] or None,
                    'validation_error': e['validation_error']
                })
        else:
            model = CR_staging_Receivable_entries
            for e in entries:
                db_entries.append({
                    'file_id': file_id,
                    'value_date': e['value_date'] or None,
                    'portfolio_id': e['portfolio_id'] or None,
                    'vch_id': e['vch_id'] or None,
                    'cr_amount': e['amount'],          # None stored as NULL when missing
                    'transaction_name': e['transaction_name'] or None,
                    'validation_error': e['validation_error']
                })
        
        db.bulk_insert_mappings(model, db_entries)
        
        recon_file.processing_status = ProcessingStatus.COMPLETED
        recon_file.transaction_count = len(entries)
        db.commit()

        # Audit Log
        log = AuditLog(
            entity="ReconFile",
            entity_id=str(file_id),
            action="PROCESS_FILE",
            actor=actor_name,
            payload={
                "source": source.value,
                "count": len(entries),
                "status": "completed"
            }
        )
        db.add(log)
        db.commit()

    except Exception as e:
        logger.error(f"Error processing {file_id}: {e}")
        recon_file = db.query(CR_Recon_Files).filter(CR_Recon_Files.id == file_id).first()
        if recon_file:
            recon_file.processing_status = ProcessingStatus.FAILED
            recon_file.processing_error = str(e)
            db.commit()
    finally:
        db.close()

@router.post("/car-recon/ingest")
async def ingest_car_file(
    background_tasks: BackgroundTasks,
    source: CR_SourceEnum,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key)
):
    uploader = SecureUpload()
    temp_path, file_hash, file_size = await uploader.save_upload_to_tmp(file)
    
    existing = db.query(CR_Recon_Files).filter(
        CR_Recon_Files.file_checksum == f"{file_hash}_{file.filename}"
    ).first()
    
    if existing:
        if os.path.exists(temp_path): os.remove(temp_path)
        # If existing but failed, maybe allow re-upload? 
        # For now, strict duplicate check
        raise HTTPException(status_code=409, detail="File already exists")

    final_path = uploader.move_to_upload_dir(temp_path, f"{file_hash}_{file.filename}")
    
    recon_file = CR_Recon_Files(
        source=source,
        file_name=file.filename,
        file_checksum=f"{file_hash}_{file.filename}",
        gcs_path=str(final_path),
        mime_type="text/csv",
        file_size_bytes=file_size,
        loaded_by=actor.name or actor.id,
        processing_status=ProcessingStatus.PROCESSING,
        transaction_count=0
    )
    db.add(recon_file)
    db.commit()
    db.refresh(recon_file)
    
    background_tasks.add_task(
        process_car_file_async,
        recon_file.id,
        str(final_path),
        source,
        actor.name or actor.id
    )
    
    return {"message": "File Uploaded", "file_id": recon_file.id}

@router.get("/car-recon/files")
def list_files(source: CR_SourceEnum = None, db: Session = Depends(get_db)):
    q = db.query(CR_Recon_Files)
    if source:
        q = q.filter(CR_Recon_Files.source == source)
    return q.order_by(CR_Recon_Files.loaded_at.desc()).limit(50).all()

@router.get("/car-recon/ingest/status/{file_id}")
def get_ingest_status(file_id: int, db: Session = Depends(get_db)):
    f = db.query(CR_Recon_Files).filter(CR_Recon_Files.id == file_id).first()
    if not f: raise HTTPException(404, "File not found")
    return {
        "file_id": f.id,
        "status": f.processing_status,
        "error": f.processing_error,
        "count": f.transaction_count
    }

# --- RECON ---

class RunCarReconRequest(BaseModel):
    cash_file_id: int
    receivable_file_id: int
    tolerance_amount: Optional[float] = 0.0
    date_window_days: Optional[int] = 0

@router.post("/car-recon/run")
def run_car_recon(req: RunCarReconRequest, db: Session = Depends(get_db), actor: Actor = Security(get_api_key)):
    engine = CarReconEngine(db)
    try:
        batch_id = engine.run_batch(
            req.cash_file_id, 
            req.receivable_file_id, 
            actor.name or actor.id,
            tolerance_amount=req.tolerance_amount,
            date_window_days=req.date_window_days
        )
        
        # Audio Log
        log = AuditLog(
            entity="ReconBatch",
            entity_id=str(batch_id),
            action="AUTO_MATCH_RUN",
            actor=actor.name or actor.id,
            payload={
                "type": "CASH_VS_AR",
                "cash_file_id": req.cash_file_id,
                "receivable_file_id": req.receivable_file_id
            }
        )
        db.add(log)
        db.commit()

        return get_latest_car_recon(db, actor)
    except Exception as e:
        logger.error(f"Recon Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _build_car_response(batch_id: int, db: Session):
    matches = db.query(CR_recon_matches).filter(CR_recon_matches.batch_id == batch_id).all()
    
    # Pre-fetch trails to check validity (Filter BREAK/DISSOLVE)
    subquery = db.query(
        CR_recon_matches_trail.CR_recon_match_ID,
        CR_recon_matches_trail.Action,
        func.row_number().over(
            partition_by=CR_recon_matches_trail.CR_recon_match_ID,
            order_by=CR_recon_matches_trail.id.desc()
        ).label("rn")
    ).filter(CR_recon_matches_trail.batch_id == batch_id).subquery()
    
    # Get the latest action for every match (used for both filtering and match_action field)
    latest_actions = {r[0]: r[1] for r in db.query(
        subquery.c.CR_recon_match_ID, subquery.c.Action
    ).filter(subquery.c.rn == 1).all()}

    invalid_ids = [mid for mid, action in latest_actions.items() if action in ("BREAK", "DISSOLVE")]
    
    matches = [m for m in matches if m.id not in invalid_ids]

    # Findings (Filter RESOLVED)
    findings = db.query(CR_recon_findings).filter(CR_recon_findings.batch_id == batch_id).all()
    
    subquery_f = db.query(
        CR_recon_findings_trail.CR_recon_finding_ID,
        CR_recon_findings_trail.Action,
        func.row_number().over(
            partition_by=CR_recon_findings_trail.CR_recon_finding_ID,
            order_by=CR_recon_findings_trail.id.desc()
        ).label("rn")
    ).filter(CR_recon_findings_trail.batch_id == batch_id).subquery()

    resolved_ids = [r[0] for r in db.query(subquery_f.c.CR_recon_finding_ID).filter(
        subquery_f.c.rn == 1,
        subquery_f.c.Action.in_(["MATCHED_MANUAL", "MATCHED_AUTO", "RESOLVED"])
    ).all()]
    
    findings = [f for f in findings if f.id not in resolved_ids]

    # Fetch Entries
    batch = db.query(CR_recon_batches).filter(CR_recon_batches.id == batch_id).first()
    if not batch: return {}
    
    cash_entries = {e.id: e for e in db.query(CR_staging_Cash_entries).filter(CR_staging_Cash_entries.file_id == batch.cash_file_id).all()}
    ar_entries = {e.id: e for e in db.query(CR_staging_Receivable_entries).filter(CR_staging_Receivable_entries.file_id == batch.receivable_file_id).all()}

    res_cash = []
    res_ar = []
    
    matched_cash_ids = set()
    matched_ar_ids = set()

    def fmt(e, status, match_id="", reason="", kind=None, match_action=""):
        is_cash = hasattr(e, 'db_amount')
        raw_amt = e.db_amount if is_cash else e.cr_amount
        amt = float(raw_amt) if raw_amt is not None else 0.0   # None = missing amount (exception)
        return {
            "id": str(e.id),
            "Date": e.value_date.isoformat() if e.value_date else None,
            "PortfolioID": e.portfolio_id,
            "VchID": e.vch_id,
            "Transaction": e.transaction_name,
            "Debit": abs(amt) if is_cash else 0.0,
            "Credit": abs(amt) if not is_cash else 0.0,
            "match_status": status,
            "match_kind": kind,
            "match_id": match_id,
            "match_action": match_action,   # e.g. "MANUAL_SPLIT" or "MANUAL_MATCH"
            "reason": reason,
            "validation_error": e.validation_error
        }

    for m in matches:
        m_action = latest_actions.get(m.id, "")
        if m.cash_entry_id in cash_entries:
            res_cash.append(fmt(cash_entries[m.cash_entry_id], "MATCHED", m.match_id, m.reason, m.match_kind.value, m_action))
            matched_cash_ids.add(m.cash_entry_id)
        if m.receivable_entry_id in ar_entries:
            res_ar.append(fmt(ar_entries[m.receivable_entry_id], "MATCHED", m.match_id, m.reason, m.match_kind.value, m_action))
            matched_ar_ids.add(m.receivable_entry_id)
            
    for f in findings:
        side = f.side.name if hasattr(f.side, 'name') else str(f.side)
        if side == "CASH" and f.entry_id in cash_entries and f.entry_id not in matched_cash_ids:
            res_cash.append(fmt(cash_entries[f.entry_id], f.finding_type.value, "", f.finding_reason))
            matched_cash_ids.add(f.entry_id)
        elif side == "RECEIVABLE" and f.entry_id in ar_entries and f.entry_id not in matched_ar_ids:
            res_ar.append(fmt(ar_entries[f.entry_id], f.finding_type.value, "", f.finding_reason))
            matched_ar_ids.add(f.entry_id)
            
    summary = {
        "total_matches": len(matches),
        "auto_match_count": sum(1 for m in matches if m.match_kind == MatchKind.AUTO),
        "manual_match_count": sum(1 for m in matches if m.match_kind == MatchKind.MANUAL),
        "unmatched_count": len([x for x in res_cash + res_ar if x['match_status'] == 'UNMATCHED']),
        "exception_count": len([x for x in res_cash + res_ar if x['match_status'] == 'EXCEPTION'])
    }
    
    return {
        "batch_id": batch.id,
        "cash_file_id": batch.cash_file_id,
        "receivable_file_id": batch.receivable_file_id,
        "cash_records": res_cash,
        "ar_records": res_ar,
        "summary": summary
    }


@router.get("/car-recon/latest")
def get_latest_car_recon(db: Session = Depends(get_db), actor: Actor = Security(get_api_key)):
    batches = db.query(CR_recon_batches).order_by(CR_recon_batches.id.desc()).all()
    if not batches: return {"message": "No history"}
    
    combined_cash = []
    combined_ar = []
    total_summary = {"total_matches": 0, "auto_match_count": 0, "manual_match_count": 0, "unmatched_count": 0, "exception_count": 0}
    
    # Logic: Only get data from latest batch? Or all? Reuse recon.py logic -> all batches
    for b in batches:
        data = _build_car_response(b.id, db)
        if not data: continue
        combined_cash.extend(data.get("cash_records", []))
        combined_ar.extend(data.get("ar_records", []))
        
        s = data.get("summary", {})
        for k in total_summary:
            total_summary[k] += s.get(k, 0)
            
    latest = batches[0]
    return {
        "batch_id": latest.id,
        "cash_file_id": latest.cash_file_id,
        "receivable_file_id": latest.receivable_file_id,
        "cash_records": combined_cash,
        "ar_records": combined_ar,
        "summary": total_summary
    }

@router.get("/car-recon/status/{batch_id}")
def get_car_recon_status(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(CR_recon_batches).filter(CR_recon_batches.id == batch_id).first()
    if not batch: raise HTTPException(404, "Batch not found")
    return {
        "id": batch.id,
        "status": batch.status,
        "started_at": batch.started_at
    }

# --- MANUAL ACTIONS ---

class ManualMatchRequest(BaseModel):
    batch_id: int
    cash_entry_ids: List[int]
    ar_entry_ids: List[int]
    note: str
    manual_components: List[dict] = []  # [{"ref": str, "amount": float}]
    parent_side: str = "auto"  # "cash" | "ar" | "auto"
    
@router.post("/car-recon/manual-match")
def manual_match(req: ManualMatchRequest, db: Session = Depends(get_db), actor: Actor = Security(get_api_key)):
    batch = db.query(CR_recon_batches).filter(CR_recon_batches.id == req.batch_id).first()
    if not batch: raise HTTPException(404, "Batch not found")
    
    cash = db.query(CR_staging_Cash_entries).filter(CR_staging_Cash_entries.id.in_(req.cash_entry_ids)).all()
    ar = db.query(CR_staging_Receivable_entries).filter(CR_staging_Receivable_entries.id.in_(req.ar_entry_ids)).all()
    
    if len(cash) != len(req.cash_entry_ids) or len(ar) != len(req.ar_entry_ids):
        raise HTTPException(404, "Entries not found")
    
    total_cash = sum(abs(c.db_amount) for c in cash if c.db_amount)
    total_ar = sum(abs(a.cr_amount) for a in ar if a.cr_amount)
    
    if len(cash) == 1 and len(ar) == 1:
        # Simple Link
        c = cash[0]
        a = ar[0]
        now = datetime.utcnow()
        match = CR_recon_matches(
            batch_id=batch.id,
            cash_entry_id=c.id,
            receivable_entry_id=a.id,
            portfolio_id=c.portfolio_id,
            match_kind=MatchKind.MANUAL,
            match_id="TEMP",
            reason=req.note,
            created_by=actor.name or actor.id,
            created_at=now,
            Modified_by=actor.name or actor.id,
            Modified_at=now
        )
        db.add(match)
        db.flush()
        
        trail = CR_recon_matches_trail(
            CR_recon_match_ID=match.id,
            batch_id=batch.id,
            cash_entry_id=c.id,
            receivable_entry_id=a.id,
            portfolio_id=c.portfolio_id,
            match_kind=MatchKind.MANUAL,
            match_id="TEMP",
            reason=req.note,
            created_by=actor.name or actor.id,
            created_at=now,
            Modified_by=actor.name or actor.id,
            Modified_at=now,
            Action="MANUAL_MATCH"
        )
        db.add(trail)
        db.flush()
        match.match_id = f"PMSCAR{trail.id}"
        trail.match_id = match.match_id
        # Sync modified fields from trail to match
        match.Modified_at = trail.Modified_at
        
        # Audit Log
        log = AuditLog(
            entity="ReconMatch",
            entity_id=match.match_id,
            action="CREATE_MANUAL_MATCH_LINK",
            actor=actor.name or actor.id,
            payload={
                "type": "CASH_VS_AR",
                "batch_id": batch.id,
                "cash_entry_ids": req.cash_entry_ids,
                "ar_entry_ids": req.ar_entry_ids,
                "note": req.note
            }
        )
        db.add(log)
        
        db.commit()
        return {"message": "Matched", "match_id": match.match_id}
    
    elif len(cash) == 1 and len(ar) > 1:
        # Split Cash -> Many AR
        c = cash[0]
        manual_total = sum(abs(float(mc.get('amount', 0))) for mc in req.manual_components)
        # parent_side="cash" means cash is ONE, AR is MANY → manual adds to AR
        # parent_side="ar" means AR is ONE, cash is MANY → manual adds to cash
        if req.parent_side == "cash" or (req.parent_side == "auto" and len(cash) == 1 and len(ar) > 1):
            effective_ar = total_ar + manual_total
        else:
            effective_ar = total_ar
        if abs(total_cash - effective_ar) > 0.01:
            raise HTTPException(400, f"Amount mismatch: {total_cash} vs {effective_ar}")
            
        new_matches = []
        for a in ar:
            split_cash = CR_staging_Cash_entries(
                file_id=c.file_id,
                value_date=c.value_date,
                portfolio_id=c.portfolio_id,
                vch_id=c.vch_id,
                db_amount=a.cr_amount,
                transaction_name=f"{c.transaction_name} (Split)",
                validation_error=None
            )
            db.add(split_cash)
            db.flush()
            
            now = datetime.utcnow()
            match = CR_recon_matches(
                batch_id=batch.id,
                cash_entry_id=split_cash.id,
                receivable_entry_id=a.id,
                portfolio_id=c.portfolio_id,
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",
                reason=req.note,
                created_by=actor.name or actor.id,
                created_at=now,
                Modified_by=actor.name or actor.id,
                Modified_at=now
            )
            db.add(match)
            db.flush()
            
            trail = CR_recon_matches_trail(
                CR_recon_match_ID=match.id,
                batch_id=batch.id,
                cash_entry_id=split_cash.id,
                receivable_entry_id=a.id,
                portfolio_id=c.portfolio_id,
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",
                reason=req.note,
                created_by=actor.name or actor.id,
                created_at=now,
                Modified_by=actor.name or actor.id,
                Modified_at=now,
                Action="MANUAL_SPLIT"
            )
            db.add(trail)
            db.flush()
            match.match_id = f"PMSCAR{trail.id}"
            trail.match_id = match.match_id
            # Sync modified fields from trail to match
            match.Modified_by = trail.Modified_by
            match.Modified_at = trail.Modified_at
            new_matches.append(match.match_id)
        
        # Manual components: create synthetic AR entry + match
        for mc in req.manual_components:
            mc_amt = float(mc.get('amount', 0))
            mc_ref = mc.get('ref', c.vch_id)
            split_cash_mc = CR_staging_Cash_entries(
                file_id=c.file_id, value_date=c.value_date,
                portfolio_id=c.portfolio_id, vch_id=mc_ref,
                db_amount=mc_amt, transaction_name=f"{c.transaction_name} (Manual Split)",
                validation_error=None
            )
            db.add(split_cash_mc)
            db.flush()
            mc_ar = CR_staging_Receivable_entries(
                file_id=c.file_id, value_date=c.value_date,
                portfolio_id=c.portfolio_id, vch_id=mc_ref,
                cr_amount=mc_amt, transaction_name=f"{c.transaction_name} (Manual Split)",
                validation_error=None
            )
            db.add(mc_ar)
            db.flush()
            now_mc = datetime.utcnow()
            mc_match = CR_recon_matches(
                batch_id=batch.id, cash_entry_id=split_cash_mc.id,
                receivable_entry_id=mc_ar.id, portfolio_id=c.portfolio_id,
                match_kind=MatchKind.MANUAL, match_id="TEMP", reason=req.note,
                created_by=actor.name or actor.id, created_at=now_mc,
                Modified_by=actor.name or actor.id, Modified_at=now_mc
            )
            db.add(mc_match)
            db.flush()
            mc_trail = CR_recon_matches_trail(
                CR_recon_match_ID=mc_match.id, batch_id=batch.id,
                cash_entry_id=split_cash_mc.id, receivable_entry_id=mc_ar.id,
                portfolio_id=c.portfolio_id, match_kind=MatchKind.MANUAL,
                match_id="TEMP", reason=req.note,
                created_by=actor.name or actor.id, created_at=now_mc,
                Modified_by=actor.name or actor.id, Modified_at=now_mc,
                Action="MANUAL_SPLIT"
            )
            db.add(mc_trail)
            db.flush()
            mc_match.match_id = f"PMSCAR{mc_trail.id}"
            mc_trail.match_id = mc_match.match_id
            new_matches.append(mc_match.match_id)
        
        db.delete(c)
        
        # Audit Log
        log = AuditLog(
            entity="ReconMatch",
            entity_id="MULTIPLE",
            action="CREATE_MANUAL_MATCH_SPLIT",
            actor=actor.name or actor.id,
            payload={
                "type": "CASH_VS_AR",
                "subtype": "SPLIT_CASH_TO_MANY_AR",
                "batch_id": batch.id,
                "original_cash_id": c.id,
                "match_ids": new_matches,
                "note": req.note
            }
        )
        db.add(log)
        
        db.commit()
        return {"message": "Split & Matched", "match_ids": new_matches}

    elif len(cash) > 1 and len(ar) == 1:
        # Split AR -> Many Cash
        a = ar[0]
        manual_total = sum(abs(float(mc.get('amount', 0))) for mc in req.manual_components)
        # parent_side="ar" means AR is ONE, cash is MANY → manual adds to cash
        if req.parent_side == "ar" or (req.parent_side == "auto" and len(ar) == 1 and len(cash) > 1):
            effective_cash = total_cash + manual_total
        else:
            effective_cash = total_cash
        if abs(effective_cash - total_ar) > 0.01:
             raise HTTPException(400, f"Amount mismatch: {effective_cash} vs {total_ar}")
             
        new_matches = []
        for c in cash:
            split_ar = CR_staging_Receivable_entries(
                file_id=a.file_id,
                value_date=a.value_date,
                portfolio_id=a.portfolio_id,
                vch_id=a.vch_id,
                cr_amount=c.db_amount,
                transaction_name=f"{a.transaction_name} (Split)",
                validation_error=None
            )
            db.add(split_ar)
            db.flush()
            
            now = datetime.utcnow()
            match = CR_recon_matches(
                batch_id=batch.id,
                cash_entry_id=c.id,
                receivable_entry_id=split_ar.id,
                portfolio_id=a.portfolio_id,
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",
                reason=req.note,
                created_by=actor.name or actor.id,
                created_at=now,
                Modified_by=actor.name or actor.id,
                Modified_at=now
            )
            db.add(match)
            db.flush()
            
            trail = CR_recon_matches_trail(
                CR_recon_match_ID=match.id,
                batch_id=batch.id,
                cash_entry_id=c.id,
                receivable_entry_id=split_ar.id,
                portfolio_id=a.portfolio_id,
                match_kind=MatchKind.MANUAL,
                match_id="TEMP",
                reason=req.note,
                created_by=actor.name or actor.id,
                created_at=now,
                Modified_by=actor.name or actor.id,
                Modified_at=now,
                Action="MANUAL_SPLIT"
            )
            db.add(trail)
            db.flush()
            match.match_id = f"PMSCAR{trail.id}"
            trail.match_id = match.match_id
            # Sync modified fields from trail to match
            match.Modified_by = trail.Modified_by
            match.Modified_at = trail.Modified_at
            new_matches.append(match.match_id)
        
        # Manual components: create synthetic Cash + AR entries + match
        for mc in req.manual_components:
            mc_amt = float(mc.get('amount', 0))
            mc_ref = mc.get('ref', a.vch_id)
            mc_cash = CR_staging_Cash_entries(
                file_id=a.file_id, value_date=a.value_date,
                portfolio_id=a.portfolio_id, vch_id=mc_ref,
                db_amount=mc_amt, transaction_name=f"{a.transaction_name} (Manual Split)",
                validation_error=None
            )
            db.add(mc_cash)
            db.flush()
            mc_ar_part = CR_staging_Receivable_entries(
                file_id=a.file_id, value_date=a.value_date,
                portfolio_id=a.portfolio_id, vch_id=mc_ref,
                cr_amount=mc_amt, transaction_name=f"{a.transaction_name} (Manual Split)",
                validation_error=None
            )
            db.add(mc_ar_part)
            db.flush()
            now_mc = datetime.utcnow()
            mc_match = CR_recon_matches(
                batch_id=batch.id, cash_entry_id=mc_cash.id,
                receivable_entry_id=mc_ar_part.id, portfolio_id=a.portfolio_id,
                match_kind=MatchKind.MANUAL, match_id="TEMP", reason=req.note,
                created_by=actor.name or actor.id, created_at=now_mc,
                Modified_by=actor.name or actor.id, Modified_at=now_mc
            )
            db.add(mc_match)
            db.flush()
            mc_trail = CR_recon_matches_trail(
                CR_recon_match_ID=mc_match.id, batch_id=batch.id,
                cash_entry_id=mc_cash.id, receivable_entry_id=mc_ar_part.id,
                portfolio_id=a.portfolio_id, match_kind=MatchKind.MANUAL,
                match_id="TEMP", reason=req.note,
                created_by=actor.name or actor.id, created_at=now_mc,
                Modified_by=actor.name or actor.id, Modified_at=now_mc,
                Action="MANUAL_SPLIT"
            )
            db.add(mc_trail)
            db.flush()
            mc_match.match_id = f"PMSCAR{mc_trail.id}"
            mc_trail.match_id = mc_match.match_id
            new_matches.append(mc_match.match_id)
        
        db.delete(a)
        
        # Audit Log
        log = AuditLog(
            entity="ReconMatch",
            entity_id="MULTIPLE",
            action="CREATE_MANUAL_MATCH_SPLIT",
            actor=actor.name or actor.id,
            payload={
                "type": "CASH_VS_AR",
                "subtype": "SPLIT_AR_TO_MANY_CASH",
                "batch_id": batch.id,
                "original_ar_id": a.id,
                "match_ids": new_matches,
                "note": req.note
            }
        )
        db.add(log)
        
        db.commit()
        return {"message": "Split & Matched", "match_ids": new_matches}

    raise HTTPException(400, "Unsupported match combination")


class BreakMatchRequest(BaseModel):
    batch_id: int
    match_id: str # PMSCAR...
    reason: str

@router.post("/car-recon/match/break")
def break_match(req: BreakMatchRequest, db: Session = Depends(get_db), actor: Actor = Security(get_api_key)):
    match = db.query(CR_recon_matches).filter(CR_recon_matches.match_id == req.match_id).first()
    if not match: raise HTTPException(404, "Match not found")

    now = datetime.utcnow()
    trail = CR_recon_matches_trail(
        CR_recon_match_ID=match.id,
        batch_id=match.batch_id,
        cash_entry_id=match.cash_entry_id,
        receivable_entry_id=match.receivable_entry_id,
        portfolio_id=match.portfolio_id,
        match_kind=match.match_kind,
        match_id=match.match_id,
        reason=req.reason,
        created_by=match.created_by,
        created_at=match.created_at,
        Modified_by=actor.name or actor.id,
        Modified_at=now,
        Action="BREAK"
    )
    db.add(trail)
    db.flush()
    # Sync latest action's modified fields back to the match record
    match.Modified_by = trail.Modified_by
    match.Modified_at = trail.Modified_at

    def restore(side, entry_id, pid):
        now_f = datetime.utcnow()
        f = CR_recon_findings(
            batch_id=match.batch_id,
            side=side,
            entry_id=entry_id,
            portfolio_id=pid,
            finding_type=FindingType.UNMATCHED,
            finding_reason="Match Broken: " + req.reason,
            created_by=actor.name or actor.id,
            created_at=now_f,
            Modified_by=actor.name or actor.id,
            Modified_at=now_f
        )
        db.add(f)
        db.flush()

        ft = CR_recon_findings_trail(
            CR_recon_finding_ID=f.id,
            batch_id=match.batch_id,
            side=side,
            entry_id=entry_id,
            portfolio_id=pid,
            finding_type=FindingType.UNMATCHED,
            finding_reason=f.finding_reason,
            created_by=actor.name or actor.id,
            created_at=now_f,
            Modified_by=actor.name or actor.id,
            Modified_at=now_f,
            Action="CREATED"
        )
        db.add(ft)

    if match.cash_entry_id:
        restore(FindingSide.CASH, match.cash_entry_id, match.portfolio_id)
    if match.receivable_entry_id:
        restore(FindingSide.RECEIVABLE, match.receivable_entry_id, match.portfolio_id)

    db.commit()
    
    # Audit Log
    log = AuditLog(
        entity="ReconMatch",
        entity_id=match.match_id,
        action="BREAK_MATCH",
        actor=actor.name or actor.id,
        payload={
            "type": "CASH_VS_AR",
            "batch_id": match.batch_id,
            "reason": req.reason
        }
    )
    db.add(log)
    db.commit()

    return {"message": "Match Broken"}

class DissolveMatchRequest(BaseModel):
    match_id: str   # Single PMSCAR... match ID (same as Bank vs Broker)
    batch_id: int

@router.post("/car-recon/match/dissolve")
def dissolve_match(req: DissolveMatchRequest, db: Session = Depends(get_db), actor: Actor = Security(get_api_key)):
    from decimal import Decimal

    # 1. Find the target match
    target_match = db.query(CR_recon_matches).filter(
        CR_recon_matches.batch_id == req.batch_id,
        CR_recon_matches.match_id == req.match_id
    ).first()

    if not target_match:
        raise HTTPException(404, "Match not found")

    # 2. Verify it is a SPLIT match by checking the trail action
    latest_trail = db.query(CR_recon_matches_trail).filter(
        CR_recon_matches_trail.CR_recon_match_ID == target_match.id
    ).order_by(CR_recon_matches_trail.id.desc()).first()

    if not latest_trail or latest_trail.Action != "MANUAL_SPLIT":
        raise HTTPException(400, "Only Split Matches can be dissolved.")

    # 3. Find all sibling split matches in the same batch for the same portfolio/vch_id group
    #    We identify siblings by looking for entries with "(Split)" in their name
    #    that share the same portfolio_id and batch_id.
    #    Strategy: fetch cash and AR entries for this match, detect which side is split,
    #    then find all matches in this batch that reference split entries on that side.

    cash_entry = db.query(CR_staging_Cash_entries).filter(
        CR_staging_Cash_entries.id == target_match.cash_entry_id
    ).first()
    ar_entry = db.query(CR_staging_Receivable_entries).filter(
        CR_staging_Receivable_entries.id == target_match.receivable_entry_id
    ).first()

    cash_is_split = cash_entry and "(Split)" in (cash_entry.transaction_name or "")
    ar_is_split = ar_entry and "(Split)" in (ar_entry.transaction_name or "")

    if not cash_is_split and not ar_is_split:
        raise HTTPException(400, "This match does not appear to be a Split match.")

    # 4. Find all sibling matches (same batch, same split side, same portfolio + vch_id)
    if cash_is_split:
        # Cash was split — find all cash entries with "(Split)" that share same portfolio/vch_id
        sibling_cash = db.query(CR_staging_Cash_entries).filter(
            CR_staging_Cash_entries.file_id == cash_entry.file_id,
            CR_staging_Cash_entries.portfolio_id == cash_entry.portfolio_id,
            CR_staging_Cash_entries.vch_id == cash_entry.vch_id,
            CR_staging_Cash_entries.transaction_name.like("% (Split)")
        ).all()
        sibling_cash_ids = [e.id for e in sibling_cash]

        # Find all active matches referencing these split cash entries
        group_matches = db.query(CR_recon_matches).filter(
            CR_recon_matches.batch_id == req.batch_id,
            CR_recon_matches.cash_entry_id.in_(sibling_cash_ids)
        ).all()
    else:
        # AR was split — find all ar entries with "(Split)" that share same portfolio/vch_id
        sibling_ar = db.query(CR_staging_Receivable_entries).filter(
            CR_staging_Receivable_entries.file_id == ar_entry.file_id,
            CR_staging_Receivable_entries.portfolio_id == ar_entry.portfolio_id,
            CR_staging_Receivable_entries.vch_id == ar_entry.vch_id,
            CR_staging_Receivable_entries.transaction_name.like("% (Split)")
        ).all()
        sibling_ar_ids = [e.id for e in sibling_ar]

        group_matches = db.query(CR_recon_matches).filter(
            CR_recon_matches.batch_id == req.batch_id,
            CR_recon_matches.receivable_entry_id.in_(sibling_ar_ids)
        ).all()

    if not group_matches:
        raise HTTPException(404, "Split group not found")

    # 5. Collect all cash and AR entry IDs from the group
    cash_ids = [m.cash_entry_id for m in group_matches if m.cash_entry_id]
    ar_ids = [m.receivable_entry_id for m in group_matches if m.receivable_entry_id]

    split_cash_entries = db.query(CR_staging_Cash_entries).filter(CR_staging_Cash_entries.id.in_(cash_ids)).all()
    split_ar_entries = db.query(CR_staging_Receivable_entries).filter(CR_staging_Receivable_entries.id.in_(ar_ids)).all()

    try:
        # 6. Delete all group matches and their trails
        for m in group_matches:
            db.query(CR_recon_matches_trail).filter(
                CR_recon_matches_trail.CR_recon_match_ID == m.id
            ).delete()
            db.delete(m)

        # 7. Restore the split side and create findings for the other side
        if cash_is_split:
            children = split_cash_entries
            if not children:
                raise HTTPException(400, "No cash split entries found")

            first = children[0]
            total_amt = sum(Decimal(str(c.db_amount or 0)) for c in children)
            original_name = first.transaction_name.replace(" (Split)", "").strip() if first.transaction_name else "Unknown"

            restored_cash = CR_staging_Cash_entries(
                file_id=first.file_id,
                value_date=first.value_date,
                portfolio_id=first.portfolio_id,
                vch_id=first.vch_id,
                db_amount=float(total_amt),
                transaction_name=original_name,
                validation_error=None
            )
            db.add(restored_cash)
            for child in children:
                db.delete(child)

            db.flush()

            # Create finding for restored cash parent
            now_d = datetime.utcnow()
            f_cash = CR_recon_findings(
                batch_id=req.batch_id,
                side=FindingSide.CASH,
                entry_id=restored_cash.id,
                portfolio_id=restored_cash.portfolio_id,
                finding_type=FindingType.UNMATCHED,
                finding_reason="Restored from Dissolve",
                created_by=actor.name or actor.id,
                created_at=now_d,
                Modified_by=actor.name or actor.id,
                Modified_at=now_d
            )
            db.add(f_cash)
            db.flush()

            ft_cash = CR_recon_findings_trail(
                CR_recon_finding_ID=f_cash.id,
                batch_id=req.batch_id,
                side=f_cash.side,
                entry_id=f_cash.entry_id,
                portfolio_id=f_cash.portfolio_id,
                finding_type=f_cash.finding_type,
                finding_reason=f_cash.finding_reason,
                created_by=f_cash.created_by,
                created_at=now_d,
                Modified_by=actor.name or actor.id,
                Modified_at=now_d,
                Action="CREATED"
            )
            db.add(ft_cash)

            # Restore AR entries as unmatched findings
            for a in split_ar_entries:
                now_da = datetime.utcnow()
                f_ar = CR_recon_findings(
                    batch_id=req.batch_id,
                    side=FindingSide.RECEIVABLE,
                    entry_id=a.id,
                    portfolio_id=a.portfolio_id,
                    finding_type=FindingType.UNMATCHED,
                    finding_reason="Unmatched via Dissolve",
                    created_by=actor.name or actor.id,
                    created_at=now_da,
                    Modified_by=actor.name or actor.id,
                    Modified_at=now_da
                )
                db.add(f_ar)
                db.flush()
                ft_ar = CR_recon_findings_trail(
                    CR_recon_finding_ID=f_ar.id,
                    batch_id=req.batch_id,
                    side=f_ar.side,
                    entry_id=f_ar.entry_id,
                    portfolio_id=f_ar.portfolio_id,
                    finding_type=f_ar.finding_type,
                    finding_reason=f_ar.finding_reason,
                    created_by=f_ar.created_by,
                    created_at=now_da,
                    Modified_by=actor.name or actor.id,
                    Modified_at=now_da,
                    Action="CREATED"
                )
                db.add(ft_ar)

        else:
            # AR was split
            children = split_ar_entries
            if not children:
                raise HTTPException(400, "No AR split entries found")

            first = children[0]
            total_amt = sum(Decimal(str(a.cr_amount or 0)) for a in children)
            original_name = first.transaction_name.replace(" (Split)", "").strip() if first.transaction_name else "Unknown"

            restored_ar = CR_staging_Receivable_entries(
                file_id=first.file_id,
                value_date=first.value_date,
                portfolio_id=first.portfolio_id,
                vch_id=first.vch_id,
                cr_amount=float(total_amt),
                transaction_name=original_name,
                validation_error=None
            )
            db.add(restored_ar)
            for child in children:
                db.delete(child)

            db.flush()

            # Create finding for restored AR parent
            now_d = datetime.utcnow()
            f_ar = CR_recon_findings(
                batch_id=req.batch_id,
                side=FindingSide.RECEIVABLE,
                entry_id=restored_ar.id,
                portfolio_id=restored_ar.portfolio_id,
                finding_type=FindingType.UNMATCHED,
                finding_reason="Restored from Dissolve",
                created_by=actor.name or actor.id,
                created_at=now_d,
                Modified_by=actor.name or actor.id,
                Modified_at=now_d
            )
            db.add(f_ar)
            db.flush()

            ft_ar = CR_recon_findings_trail(
                CR_recon_finding_ID=f_ar.id,
                batch_id=req.batch_id,
                side=f_ar.side,
                entry_id=f_ar.entry_id,
                portfolio_id=f_ar.portfolio_id,
                finding_type=f_ar.finding_type,
                finding_reason=f_ar.finding_reason,
                created_by=f_ar.created_by,
                created_at=now_d,
                Modified_by=actor.name or actor.id,
                Modified_at=now_d,
                Action="CREATED"
            )
            db.add(ft_ar)

            # Restore Cash entries as unmatched findings
            for c in split_cash_entries:
                now_dc = datetime.utcnow()
                f_cash = CR_recon_findings(
                    batch_id=req.batch_id,
                    side=FindingSide.CASH,
                    entry_id=c.id,
                    portfolio_id=c.portfolio_id,
                    finding_type=FindingType.UNMATCHED,
                    finding_reason="Unmatched via Dissolve",
                    created_by=actor.name or actor.id,
                    created_at=now_dc,
                    Modified_by=actor.name or actor.id,
                    Modified_at=now_dc
                )
                db.add(f_cash)
                db.flush()
                ft_cash = CR_recon_findings_trail(
                    CR_recon_finding_ID=f_cash.id,
                    batch_id=req.batch_id,
                    side=f_cash.side,
                    entry_id=f_cash.entry_id,
                    portfolio_id=f_cash.portfolio_id,
                    finding_type=f_cash.finding_type,
                    finding_reason=f_cash.finding_reason,
                    created_by=f_cash.created_by,
                    created_at=now_dc,
                    Modified_by=actor.name or actor.id,
                    Modified_at=now_dc,
                    Action="CREATED"
                )
                db.add(ft_cash)

    except Exception as e:
        logger.error(f"Error dissolving CAR split: {e}")
        db.rollback()
        raise HTTPException(500, f"Failed to dissolve split: {str(e)}")

    # Audit Log
    log = AuditLog(
        entity="ReconMatch",
        entity_id=req.match_id,
        action="DISSOLVE_MATCH",
        actor=actor.name or actor.id,
        payload={
            "type": "CASH_VS_AR",
            "batch_id": req.batch_id
        }
    )
    db.add(log)

    db.commit()
    return {"message": "Split Match Dissolved Successfully"}

