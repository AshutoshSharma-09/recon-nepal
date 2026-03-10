from fastapi import APIRouter, Depends, HTTPException, Security, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db, SessionLocal
from app.engine.cap_core import CapReconEngine
from app.models import (
    CAP_recon_batches, CAP_recon_matches, CAP_recon_findings, BatchStatus,
    CAP_staging_Cash_entries, CAP_staging_Payable_entries,
    MatchKind, CAP_SourceEnum, FindingType, FindingSide,
    CAP_recon_matches_trail, CAP_recon_findings_trail,
    CAP_Recon_Files, ProcessingStatus, AuditLog
)
from pydantic import BaseModel
from app.core.security import get_api_key, Actor
from app.core.upload import SecureUpload
from app.ingestion.parsers import CashApCsvParser
import logging
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import os

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================
# INGESTION
# ============================================================

def process_cap_file_async(file_id: int, file_path: str, source: CAP_SourceEnum, actor_name: str):
    db = SessionLocal()
    source_str = "CASH" if source == CAP_SourceEnum.CASH else "PAYABLE"
    parser = CashApCsvParser(source=source_str)

    try:
        recon_file = db.query(CAP_Recon_Files).filter(CAP_Recon_Files.id == file_id).first()
        if not recon_file:
            return

        recon_file.processing_status = ProcessingStatus.PROCESSING
        db.commit()

        entries = parser.parse(Path(file_path).read_bytes())

        if not entries:
            recon_file.processing_status = ProcessingStatus.FAILED
            recon_file.processing_error = "No valid transactions found"
            db.commit()
            return

        db_entries = []
        if source == CAP_SourceEnum.CASH:
            model = CAP_staging_Cash_entries
            for e in entries:
                db_entries.append({
                    'file_id': file_id,
                    'value_date': e['value_date'] or None,
                    'portfolio_id': e['portfolio_id'] or None,
                    'vch_id': e['vch_id'] or None,
                    'credit_amount': e['amount'],   # Credit_Amount column
                    'transaction_name': e['transaction_name'] or None,
                    'validation_error': e['validation_error']
                })
        else:
            model = CAP_staging_Payable_entries
            for e in entries:
                db_entries.append({
                    'file_id': file_id,
                    'value_date': e['value_date'] or None,
                    'portfolio_id': e['portfolio_id'] or None,
                    'vch_id': e['vch_id'] or None,
                    'debit_amount': e['amount'],    # DB_Amount column
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
        logger.error(f"Error processing CAP file {file_id}: {e}")
        recon_file = db.query(CAP_Recon_Files).filter(CAP_Recon_Files.id == file_id).first()
        if recon_file:
            recon_file.processing_status = ProcessingStatus.FAILED
            recon_file.processing_error = str(e)
            db.commit()
    finally:
        db.close()


@router.post("/cap-recon/ingest")
async def ingest_cap_file(
    background_tasks: BackgroundTasks,
    source: CAP_SourceEnum,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key)
):
    uploader = SecureUpload()
    temp_path, file_hash, file_size = await uploader.save_upload_to_tmp(file)

    existing = db.query(CAP_Recon_Files).filter(
        CAP_Recon_Files.file_checksum == f"{file_hash}_{file.filename}"
    ).first()

    if existing:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=409, detail="File already exists")

    final_path = uploader.move_to_upload_dir(temp_path, f"{file_hash}_{file.filename}")

    recon_file = CAP_Recon_Files(
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
        process_cap_file_async,
        recon_file.id,
        str(final_path),
        source,
        actor.name or actor.id
    )

    return {"message": "File Uploaded", "file_id": recon_file.id}


@router.get("/cap-recon/files")
def list_cap_files(source: CAP_SourceEnum = None, db: Session = Depends(get_db)):
    q = db.query(CAP_Recon_Files)
    if source:
        q = q.filter(CAP_Recon_Files.source == source)
    return q.order_by(CAP_Recon_Files.loaded_at.desc()).limit(50).all()


@router.get("/cap-recon/ingest/status/{file_id}")
def get_cap_ingest_status(file_id: int, db: Session = Depends(get_db)):
    f = db.query(CAP_Recon_Files).filter(CAP_Recon_Files.id == file_id).first()
    if not f:
        raise HTTPException(404, "File not found")
    return {
        "file_id": f.id,
        "status": f.processing_status,
        "error": f.processing_error,
        "count": f.transaction_count
    }


# ============================================================
# RECONCILIATION
# ============================================================

class RunCapReconRequest(BaseModel):
    cash_file_id: int
    payable_file_id: int
    tolerance_amount: Optional[float] = 0.0
    date_window_days: Optional[int] = 0


@router.post("/cap-recon/run")
def run_cap_recon(req: RunCapReconRequest, db: Session = Depends(get_db), actor: Actor = Security(get_api_key)):
    engine = CapReconEngine(db)
    try:
        batch_id = req.batch_id if hasattr(req, 'batch_id') else 0 # Wait, run_batch returns batch_id?
        # engine.run_batch returns batch_id?
        # In cap_recon, line 178: engine.run_batch(...) returns None? 
        # Let me check cap_core.py or verify return value. 
        # In car_recon it returned batch_id. 
        # In cap_recon.py view_file output:
        # 178: engine.run_batch(
        # ...
        # 185: return get_latest_cap_recon(db, actor)
        
        # It doesn't capture the return value in a variable. 
        # I should capture it.
        
        batch_id = engine.run_batch(
            req.cash_file_id,
            req.payable_file_id,
            actor.name or actor.id,
            tolerance_amount=req.tolerance_amount,
            date_window_days=req.date_window_days
        )
        
        # Audit Log
        log = AuditLog(
            entity="ReconBatch",
            entity_id=str(batch_id),
            action="AUTO_MATCH_RUN",
            actor=actor.name or actor.id,
            payload={
                "type": "CASH_VS_AP",
                "cash_file_id": req.cash_file_id,
                "payable_file_id": req.payable_file_id
            }
        )
        db.add(log)
        db.commit()

        return get_latest_cap_recon(db, actor)
    except Exception as e:
        logger.error(f"CAP Recon Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _build_cap_response(batch_id: int, db: Session):
    matches = db.query(CAP_recon_matches).filter(CAP_recon_matches.batch_id == batch_id).all()

    # Latest action per match (for BREAK/DISSOLVE filtering)
    subquery = db.query(
        CAP_recon_matches_trail.CAP_recon_match_ID,
        CAP_recon_matches_trail.Action,
        func.row_number().over(
            partition_by=CAP_recon_matches_trail.CAP_recon_match_ID,
            order_by=CAP_recon_matches_trail.id.desc()
        ).label("rn")
    ).filter(CAP_recon_matches_trail.batch_id == batch_id).subquery()

    latest_actions = {r[0]: r[1] for r in db.query(
        subquery.c.CAP_recon_match_ID, subquery.c.Action
    ).filter(subquery.c.rn == 1).all()}

    invalid_ids = [mid for mid, action in latest_actions.items() if action in ("BREAK", "DISSOLVE")]
    matches = [m for m in matches if m.id not in invalid_ids]

    # Findings (filter RESOLVED)
    findings = db.query(CAP_recon_findings).filter(CAP_recon_findings.batch_id == batch_id).all()

    subquery_f = db.query(
        CAP_recon_findings_trail.CAP_recon_finding_ID,
        CAP_recon_findings_trail.Action,
        func.row_number().over(
            partition_by=CAP_recon_findings_trail.CAP_recon_finding_ID,
            order_by=CAP_recon_findings_trail.id.desc()
        ).label("rn")
    ).filter(CAP_recon_findings_trail.batch_id == batch_id).subquery()

    resolved_ids = [r[0] for r in db.query(subquery_f.c.CAP_recon_finding_ID).filter(
        subquery_f.c.rn == 1,
        subquery_f.c.Action.in_(["MATCHED_MANUAL", "MATCHED_AUTO", "RESOLVED"])
    ).all()]

    findings = [f for f in findings if f.id not in resolved_ids]

    batch = db.query(CAP_recon_batches).filter(CAP_recon_batches.id == batch_id).first()
    if not batch:
        return {}

    cash_entries = {e.id: e for e in db.query(CAP_staging_Cash_entries).filter(
        CAP_staging_Cash_entries.file_id == batch.cash_file_id).all()}
    payable_entries = {e.id: e for e in db.query(CAP_staging_Payable_entries).filter(
        CAP_staging_Payable_entries.file_id == batch.payable_file_id).all()}

    res_cash = []
    res_payable = []
    matched_cash_ids = set()
    matched_payable_ids = set()

    def fmt(e, status, match_id="", reason="", kind=None, match_action=""):
        is_cash = hasattr(e, 'credit_amount')
        raw_amt = e.credit_amount if is_cash else e.debit_amount
        amt = float(raw_amt) if raw_amt is not None else 0.0
        return {
            "id": str(e.id),
            "Date": e.value_date.isoformat() if e.value_date else None,
            "PortfolioID": e.portfolio_id,
            "VchID": e.vch_id,
            "Transaction": e.transaction_name,
            "Debit": 0.0 if is_cash else abs(amt),
            "Credit": abs(amt) if is_cash else 0.0,
            "match_status": status,
            "match_kind": kind,
            "match_id": match_id,
            "match_action": match_action,
            "reason": reason,
            "validation_error": e.validation_error
        }

    for m in matches:
        m_action = latest_actions.get(m.id, "")
        if m.cash_entry_id in cash_entries:
            res_cash.append(fmt(cash_entries[m.cash_entry_id], "MATCHED", m.match_id, m.reason, m.match_kind.value, m_action))
            matched_cash_ids.add(m.cash_entry_id)
        if m.payable_entry_id in payable_entries:
            res_payable.append(fmt(payable_entries[m.payable_entry_id], "MATCHED", m.match_id, m.reason, m.match_kind.value, m_action))
            matched_payable_ids.add(m.payable_entry_id)

    for f in findings:
        side = f.side if isinstance(f.side, str) else f.side.value if hasattr(f.side, 'value') else str(f.side)
        if side == "CASH" and f.entry_id in cash_entries and f.entry_id not in matched_cash_ids:
            res_cash.append(fmt(cash_entries[f.entry_id], f.finding_type.value, "", f.finding_reason))
            matched_cash_ids.add(f.entry_id)
        elif side == "PAYABLE" and f.entry_id in payable_entries and f.entry_id not in matched_payable_ids:
            res_payable.append(fmt(payable_entries[f.entry_id], f.finding_type.value, "", f.finding_reason))
            matched_payable_ids.add(f.entry_id)

    summary = {
        "total_matches": len(matches),
        "auto_match_count": sum(1 for m in matches if m.match_kind == MatchKind.AUTO),
        "manual_match_count": sum(1 for m in matches if m.match_kind == MatchKind.MANUAL),
        "unmatched_count": len([x for x in res_cash + res_payable if x['match_status'] == 'UNMATCHED']),
        "exception_count": len([x for x in res_cash + res_payable if x['match_status'] == 'EXCEPTION'])
    }

    return {
        "batch_id": batch.id,
        "cash_file_id": batch.cash_file_id,
        "payable_file_id": batch.payable_file_id,
        "cash_records": res_cash,
        "ap_records": res_payable,
        "summary": summary
    }


@router.get("/cap-recon/latest")
def get_latest_cap_recon(db: Session = Depends(get_db), actor: Actor = Security(get_api_key)):
    batches = db.query(CAP_recon_batches).order_by(CAP_recon_batches.id.desc()).all()
    if not batches:
        return {"message": "No history"}

    combined_cash = []
    combined_ap = []
    total_summary = {"total_matches": 0, "auto_match_count": 0, "manual_match_count": 0,
                     "unmatched_count": 0, "exception_count": 0}

    for b in batches:
        data = _build_cap_response(b.id, db)
        if not data:
            continue
        combined_cash.extend(data.get("cash_records", []))
        combined_ap.extend(data.get("ap_records", []))
        s = data.get("summary", {})
        for k in total_summary:
            total_summary[k] += s.get(k, 0)

    latest = batches[0]
    return {
        "batch_id": latest.id,
        "cash_file_id": latest.cash_file_id,
        "payable_file_id": latest.payable_file_id,
        "cash_records": combined_cash,
        "ap_records": combined_ap,
        "summary": total_summary
    }


@router.get("/cap-recon/status/{batch_id}")
def get_cap_recon_status(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(CAP_recon_batches).filter(CAP_recon_batches.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")
    return {"id": batch.id, "status": batch.status, "started_at": batch.started_at}


# ============================================================
# MANUAL ACTIONS
# ============================================================

class ManualMatchCapRequest(BaseModel):
    batch_id: int
    cash_entry_ids: List[int]
    ap_entry_ids: List[int]
    note: str
    manual_components: List[dict] = []  # [{"ref": str, "amount": float}]
    parent_side: str = "auto"  # "cash" | "ap" | "auto"


@router.post("/cap-recon/manual-match")
def manual_match_cap(req: ManualMatchCapRequest, db: Session = Depends(get_db), actor: Actor = Security(get_api_key)):
    batch = db.query(CAP_recon_batches).filter(CAP_recon_batches.id == req.batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")

    cash = db.query(CAP_staging_Cash_entries).filter(CAP_staging_Cash_entries.id.in_(req.cash_entry_ids)).all()
    ap = db.query(CAP_staging_Payable_entries).filter(CAP_staging_Payable_entries.id.in_(req.ap_entry_ids)).all()

    if len(cash) != len(req.cash_entry_ids) or len(ap) != len(req.ap_entry_ids):
        raise HTTPException(404, "Entries not found")

    total_cash = sum(abs(c.credit_amount) for c in cash if c.credit_amount)
    total_ap = sum(abs(a.debit_amount) for a in ap if a.debit_amount)

    if len(cash) == 1 and len(ap) == 1:
        # Simple Link: 1-to-1
        c = cash[0]
        a = ap[0]
        now = datetime.utcnow()
        match = CAP_recon_matches(
            batch_id=batch.id,
            cash_entry_id=c.id,
            payable_entry_id=a.id,
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

        trail = CAP_recon_matches_trail(
            CAP_recon_match_ID=match.id,
            batch_id=batch.id,
            cash_entry_id=c.id,
            payable_entry_id=a.id,
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
        match.match_id = f"PMSCAP{trail.id}"
        trail.match_id = match.match_id
        match.Modified_by = trail.Modified_by
        match.Modified_at = trail.Modified_at
        
        # Audit Log
        log = AuditLog(
            entity="ReconMatch",
            entity_id=match.match_id,
            action="CREATE_MANUAL_MATCH_LINK",
            actor=actor.name or actor.id,
            payload={
                "type": "CASH_VS_AP",
                "batch_id": batch.id,
                "cash_entry_ids": req.cash_entry_ids,
                "ap_entry_ids": req.ap_entry_ids,
                "note": req.note
            }
        )
        db.add(log)
        
        db.commit()
        return {"message": "Matched", "match_id": match.match_id}

    elif len(cash) == 1 and len(ap) > 1:
        # Split: 1 Cash -> Many AP
        c = cash[0]
        manual_total = sum(abs(float(mc.get('amount', 0))) for mc in req.manual_components)
        if req.parent_side == "cash" or (req.parent_side == "auto" and len(cash) == 1 and len(ap) > 1):
            effective_ap = total_ap + manual_total
        else:
            effective_ap = total_ap
        if abs(total_cash - effective_ap) > 0.01:
            raise HTTPException(400, f"Amount mismatch: {total_cash} vs {effective_ap}")

        new_matches = []
        for a in ap:
            split_cash = CAP_staging_Cash_entries(
                file_id=c.file_id,
                value_date=c.value_date,
                portfolio_id=c.portfolio_id,
                vch_id=c.vch_id,
                credit_amount=a.debit_amount,
                transaction_name=f"{c.transaction_name} (Split)",
                validation_error=None
            )
            db.add(split_cash)
            db.flush()

            now = datetime.utcnow()
            match = CAP_recon_matches(
                batch_id=batch.id,
                cash_entry_id=split_cash.id,
                payable_entry_id=a.id,
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

            trail = CAP_recon_matches_trail(
                CAP_recon_match_ID=match.id,
                batch_id=batch.id,
                cash_entry_id=split_cash.id,
                payable_entry_id=a.id,
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
            match.match_id = f"PMSCAP{trail.id}"
            trail.match_id = match.match_id
            match.Modified_by = trail.Modified_by
            match.Modified_at = trail.Modified_at
            new_matches.append(match.match_id)
        
        # Manual components: create synthetic Cash + AP entries + match
        for mc in req.manual_components:
            mc_amt = float(mc.get('amount', 0))
            mc_ref = mc.get('ref', c.vch_id)
            mc_cash = CAP_staging_Cash_entries(
                file_id=c.file_id, value_date=c.value_date,
                portfolio_id=c.portfolio_id, vch_id=mc_ref,
                credit_amount=mc_amt, transaction_name=f"{c.transaction_name} (Manual Split)",
                validation_error=None
            )
            db.add(mc_cash)
            db.flush()
            mc_ap = CAP_staging_Payable_entries(
                file_id=c.file_id, value_date=c.value_date,
                portfolio_id=c.portfolio_id, vch_id=mc_ref,
                debit_amount=mc_amt, transaction_name=f"{c.transaction_name} (Manual Split)",
                validation_error=None
            )
            db.add(mc_ap)
            db.flush()
            now_mc = datetime.utcnow()
            mc_match = CAP_recon_matches(
                batch_id=batch.id, cash_entry_id=mc_cash.id,
                payable_entry_id=mc_ap.id, portfolio_id=c.portfolio_id,
                match_kind=MatchKind.MANUAL, match_id="TEMP", reason=req.note,
                created_by=actor.name or actor.id, created_at=now_mc,
                Modified_by=actor.name or actor.id, Modified_at=now_mc
            )
            db.add(mc_match)
            db.flush()
            mc_trail = CAP_recon_matches_trail(
                CAP_recon_match_ID=mc_match.id, batch_id=batch.id,
                cash_entry_id=mc_cash.id, payable_entry_id=mc_ap.id,
                portfolio_id=c.portfolio_id, match_kind=MatchKind.MANUAL,
                match_id="TEMP", reason=req.note,
                created_by=actor.name or actor.id, created_at=now_mc,
                Modified_by=actor.name or actor.id, Modified_at=now_mc,
                Action="MANUAL_SPLIT"
            )
            db.add(mc_trail)
            db.flush()
            mc_match.match_id = f"PMSCAP{mc_trail.id}"
            mc_trail.match_id = mc_match.match_id
            mc_match.Modified_by = mc_trail.Modified_by
            mc_match.Modified_at = mc_trail.Modified_at
            new_matches.append(mc_match.match_id)
        
        db.delete(c)
        
        # Audit Log
        log = AuditLog(
            entity="ReconMatch",
            entity_id="MULTIPLE",
            action="CREATE_MANUAL_MATCH_SPLIT",
            actor=actor.name or actor.id,
            payload={
                "type": "CASH_VS_AP",
                "subtype": "SPLIT_CASH_TO_MANY_AP",
                "batch_id": batch.id,
                "original_cash_id": c.id,
                "match_ids": new_matches,
                "note": req.note
            }
        )
        db.add(log)
        
        db.commit()
        return {"message": "Split & Matched", "match_ids": new_matches}

    elif len(cash) > 1 and len(ap) == 1:
        # Split: Many Cash -> 1 AP
        a = ap[0]
        manual_total = sum(abs(float(mc.get('amount', 0))) for mc in req.manual_components)
        if req.parent_side == "ap" or (req.parent_side == "auto" and len(ap) == 1 and len(cash) > 1):
            effective_cash = total_cash + manual_total
        else:
            effective_cash = total_cash
        if abs(effective_cash - total_ap) > 0.01:
            raise HTTPException(400, f"Amount mismatch: {effective_cash} vs {total_ap}")

        new_matches = []
        for c in cash:
            split_ap = CAP_staging_Payable_entries(
                file_id=a.file_id,
                value_date=a.value_date,
                portfolio_id=a.portfolio_id,
                vch_id=a.vch_id,
                debit_amount=c.credit_amount,
                transaction_name=f"{a.transaction_name} (Split)",
                validation_error=None
            )
            db.add(split_ap)
            db.flush()

            now = datetime.utcnow()
            match = CAP_recon_matches(
                batch_id=batch.id,
                cash_entry_id=c.id,
                payable_entry_id=split_ap.id,
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

            trail = CAP_recon_matches_trail(
                CAP_recon_match_ID=match.id,
                batch_id=batch.id,
                cash_entry_id=c.id,
                payable_entry_id=split_ap.id,
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
            match.match_id = f"PMSCAP{trail.id}"
            trail.match_id = match.match_id
            match.Modified_by = trail.Modified_by
            match.Modified_at = trail.Modified_at
            new_matches.append(match.match_id)
        
        # Manual components: create synthetic Cash + AP entries + match
        for mc in req.manual_components:
            mc_amt = float(mc.get('amount', 0))
            mc_ref = mc.get('ref', a.vch_id)
            mc_cash = CAP_staging_Cash_entries(
                file_id=a.file_id, value_date=a.value_date,
                portfolio_id=a.portfolio_id, vch_id=mc_ref,
                credit_amount=mc_amt, transaction_name=f"{a.transaction_name} (Manual Split)",
                validation_error=None
            )
            db.add(mc_cash)
            db.flush()
            mc_ap_part = CAP_staging_Payable_entries(
                file_id=a.file_id, value_date=a.value_date,
                portfolio_id=a.portfolio_id, vch_id=mc_ref,
                debit_amount=mc_amt, transaction_name=f"{a.transaction_name} (Manual Split)",
                validation_error=None
            )
            db.add(mc_ap_part)
            db.flush()
            now_mc = datetime.utcnow()
            mc_match = CAP_recon_matches(
                batch_id=batch.id, cash_entry_id=mc_cash.id,
                payable_entry_id=mc_ap_part.id, portfolio_id=a.portfolio_id,
                match_kind=MatchKind.MANUAL, match_id="TEMP", reason=req.note,
                created_by=actor.name or actor.id, created_at=now_mc,
                Modified_by=actor.name or actor.id, Modified_at=now_mc
            )
            db.add(mc_match)
            db.flush()
            mc_trail = CAP_recon_matches_trail(
                CAP_recon_match_ID=mc_match.id, batch_id=batch.id,
                cash_entry_id=mc_cash.id, payable_entry_id=mc_ap_part.id,
                portfolio_id=a.portfolio_id, match_kind=MatchKind.MANUAL,
                match_id="TEMP", reason=req.note,
                created_by=actor.name or actor.id, created_at=now_mc,
                Modified_by=actor.name or actor.id, Modified_at=now_mc,
                Action="MANUAL_SPLIT"
            )
            db.add(mc_trail)
            db.flush()
            mc_match.match_id = f"PMSCAP{mc_trail.id}"
            mc_trail.match_id = mc_match.match_id
            mc_match.Modified_by = mc_trail.Modified_by
            mc_match.Modified_at = mc_trail.Modified_at
            new_matches.append(mc_match.match_id)
        
        db.delete(a)
        
        # Audit Log
        log = AuditLog(
            entity="ReconMatch",
            entity_id="MULTIPLE",
            action="CREATE_MANUAL_MATCH_SPLIT",
            actor=actor.name or actor.id,
            payload={
                "type": "CASH_VS_AP",
                "subtype": "SPLIT_AP_TO_MANY_CASH",
                "batch_id": batch.id,
                "original_ap_id": a.id,
                "match_ids": new_matches,
                "note": req.note
            }
        )
        db.add(log)
        
        db.commit()
        return {"message": "Split & Matched", "match_ids": new_matches}

    raise HTTPException(400, "Unsupported match combination")


class BreakMatchCapRequest(BaseModel):
    batch_id: int
    match_id: str  # PMSCAP...
    reason: str


@router.post("/cap-recon/match/break")
def break_cap_match(req: BreakMatchCapRequest, db: Session = Depends(get_db), actor: Actor = Security(get_api_key)):
    match = db.query(CAP_recon_matches).filter(CAP_recon_matches.match_id == req.match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")

    now = datetime.utcnow()
    trail = CAP_recon_matches_trail(
        CAP_recon_match_ID=match.id,
        batch_id=match.batch_id,
        cash_entry_id=match.cash_entry_id,
        payable_entry_id=match.payable_entry_id,
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
    match.Modified_by = trail.Modified_by
    match.Modified_at = trail.Modified_at

    def restore(side, entry_id, pid):
        now_f = datetime.utcnow()
        f = CAP_recon_findings(
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
        ft = CAP_recon_findings_trail(
            CAP_recon_finding_ID=f.id,
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
    if match.payable_entry_id:
        restore(FindingSide.PAYABLE, match.payable_entry_id, match.portfolio_id)

    db.commit()
    db.commit()
    
    # Audit Log
    log = AuditLog(
        entity="ReconMatch",
        entity_id=match.match_id,
        action="BREAK_MATCH",
        actor=actor.name or actor.id,
        payload={
            "type": "CASH_VS_AP",
            "batch_id": match.batch_id,
            "reason": req.reason
        }
    )
    db.add(log)
    db.commit()
    
    return {"message": "Match Broken"}


class DissolveMatchCapRequest(BaseModel):
    match_id: str   # PMSCAP...
    batch_id: int


@router.post("/cap-recon/match/dissolve")
def dissolve_cap_match(req: DissolveMatchCapRequest, db: Session = Depends(get_db), actor: Actor = Security(get_api_key)):
    from decimal import Decimal

    target_match = db.query(CAP_recon_matches).filter(
        CAP_recon_matches.batch_id == req.batch_id,
        CAP_recon_matches.match_id == req.match_id
    ).first()

    if not target_match:
        raise HTTPException(404, "Match not found")

    latest_trail = db.query(CAP_recon_matches_trail).filter(
        CAP_recon_matches_trail.CAP_recon_match_ID == target_match.id
    ).order_by(CAP_recon_matches_trail.id.desc()).first()

    if not latest_trail or latest_trail.Action != "MANUAL_SPLIT":
        raise HTTPException(400, "Only Split Matches can be dissolved.")

    cash_entry = db.query(CAP_staging_Cash_entries).filter(
        CAP_staging_Cash_entries.id == target_match.cash_entry_id
    ).first()
    ap_entry = db.query(CAP_staging_Payable_entries).filter(
        CAP_staging_Payable_entries.id == target_match.payable_entry_id
    ).first()

    cash_is_split = cash_entry and "(Split)" in (cash_entry.transaction_name or "")
    ap_is_split = ap_entry and "(Split)" in (ap_entry.transaction_name or "")

    if not cash_is_split and not ap_is_split:
        raise HTTPException(400, "This match does not appear to be a Split match.")

    if cash_is_split:
        sibling_cash = db.query(CAP_staging_Cash_entries).filter(
            CAP_staging_Cash_entries.file_id == cash_entry.file_id,
            CAP_staging_Cash_entries.portfolio_id == cash_entry.portfolio_id,
            CAP_staging_Cash_entries.vch_id == cash_entry.vch_id,
            CAP_staging_Cash_entries.transaction_name.like("% (Split)")
        ).all()
        sibling_cash_ids = [e.id for e in sibling_cash]

        group_matches = db.query(CAP_recon_matches).filter(
            CAP_recon_matches.batch_id == req.batch_id,
            CAP_recon_matches.cash_entry_id.in_(sibling_cash_ids)
        ).all()
    else:
        sibling_ap = db.query(CAP_staging_Payable_entries).filter(
            CAP_staging_Payable_entries.file_id == ap_entry.file_id,
            CAP_staging_Payable_entries.portfolio_id == ap_entry.portfolio_id,
            CAP_staging_Payable_entries.vch_id == ap_entry.vch_id,
            CAP_staging_Payable_entries.transaction_name.like("% (Split)")
        ).all()
        sibling_ap_ids = [e.id for e in sibling_ap]

        group_matches = db.query(CAP_recon_matches).filter(
            CAP_recon_matches.batch_id == req.batch_id,
            CAP_recon_matches.payable_entry_id.in_(sibling_ap_ids)
        ).all()

    if not group_matches:
        raise HTTPException(404, "Split group not found")

    cash_ids = [m.cash_entry_id for m in group_matches if m.cash_entry_id]
    ap_ids = [m.payable_entry_id for m in group_matches if m.payable_entry_id]

    split_cash_entries = db.query(CAP_staging_Cash_entries).filter(CAP_staging_Cash_entries.id.in_(cash_ids)).all()
    split_ap_entries = db.query(CAP_staging_Payable_entries).filter(CAP_staging_Payable_entries.id.in_(ap_ids)).all()

    try:
        for m in group_matches:
            db.query(CAP_recon_matches_trail).filter(
                CAP_recon_matches_trail.CAP_recon_match_ID == m.id
            ).delete()
            db.delete(m)

        if cash_is_split:
            children = split_cash_entries
            if not children:
                raise HTTPException(400, "No cash split entries found")
            first = children[0]
            total_amt = sum(Decimal(str(c.credit_amount or 0)) for c in children)
            original_name = first.transaction_name.replace(" (Split)", "").strip() if first.transaction_name else "Unknown"

            restored_cash = CAP_staging_Cash_entries(
                file_id=first.file_id,
                value_date=first.value_date,
                portfolio_id=first.portfolio_id,
                vch_id=first.vch_id,
                credit_amount=float(total_amt),
                transaction_name=original_name,
                validation_error=None
            )
            db.add(restored_cash)
            for child in children:
                db.delete(child)
            db.flush()

            now_d = datetime.utcnow()
            f_cash = CAP_recon_findings(
                batch_id=req.batch_id, side=FindingSide.CASH,
                entry_id=restored_cash.id, portfolio_id=restored_cash.portfolio_id,
                finding_type=FindingType.UNMATCHED, finding_reason="Restored from Dissolve",
                created_by=actor.name or actor.id, created_at=now_d,
                Modified_by=actor.name or actor.id, Modified_at=now_d
            )
            db.add(f_cash)
            db.flush()
            db.add(CAP_recon_findings_trail(
                CAP_recon_finding_ID=f_cash.id, batch_id=req.batch_id,
                side=f_cash.side, entry_id=f_cash.entry_id,
                portfolio_id=f_cash.portfolio_id, finding_type=f_cash.finding_type,
                finding_reason=f_cash.finding_reason, created_by=f_cash.created_by,
                created_at=now_d, Modified_by=actor.name or actor.id,
                Modified_at=now_d, Action="CREATED"
            ))

            for a in split_ap_entries:
                now_da = datetime.utcnow()
                f_ap = CAP_recon_findings(
                    batch_id=req.batch_id, side=FindingSide.PAYABLE,
                    entry_id=a.id, portfolio_id=a.portfolio_id,
                    finding_type=FindingType.UNMATCHED, finding_reason="Unmatched via Dissolve",
                    created_by=actor.name or actor.id, created_at=now_da,
                    Modified_by=actor.name or actor.id, Modified_at=now_da
                )
                db.add(f_ap)
                db.flush()
                db.add(CAP_recon_findings_trail(
                    CAP_recon_finding_ID=f_ap.id, batch_id=req.batch_id,
                    side=f_ap.side, entry_id=f_ap.entry_id,
                    portfolio_id=f_ap.portfolio_id, finding_type=f_ap.finding_type,
                    finding_reason=f_ap.finding_reason, created_by=f_ap.created_by,
                    created_at=now_da, Modified_by=actor.name or actor.id,
                    Modified_at=now_da, Action="CREATED"
                ))

        else:
            children = split_ap_entries
            if not children:
                raise HTTPException(400, "No AP split entries found")
            first = children[0]
            total_amt = sum(Decimal(str(a.debit_amount or 0)) for a in children)
            original_name = first.transaction_name.replace(" (Split)", "").strip() if first.transaction_name else "Unknown"

            restored_ap = CAP_staging_Payable_entries(
                file_id=first.file_id,
                value_date=first.value_date,
                portfolio_id=first.portfolio_id,
                vch_id=first.vch_id,
                debit_amount=float(total_amt),
                transaction_name=original_name,
                validation_error=None
            )
            db.add(restored_ap)
            for child in children:
                db.delete(child)
            db.flush()

            now_d = datetime.utcnow()
            f_ap = CAP_recon_findings(
                batch_id=req.batch_id, side=FindingSide.PAYABLE,
                entry_id=restored_ap.id, portfolio_id=restored_ap.portfolio_id,
                finding_type=FindingType.UNMATCHED, finding_reason="Restored from Dissolve",
                created_by=actor.name or actor.id, created_at=now_d,
                Modified_by=actor.name or actor.id, Modified_at=now_d
            )
            db.add(f_ap)
            db.flush()
            db.add(CAP_recon_findings_trail(
                CAP_recon_finding_ID=f_ap.id, batch_id=req.batch_id,
                side=f_ap.side, entry_id=f_ap.entry_id,
                portfolio_id=f_ap.portfolio_id, finding_type=f_ap.finding_type,
                finding_reason=f_ap.finding_reason, created_by=f_ap.created_by,
                created_at=now_d, Modified_by=actor.name or actor.id,
                Modified_at=now_d, Action="CREATED"
            ))

            for c in split_cash_entries:
                now_dc = datetime.utcnow()
                f_cash = CAP_recon_findings(
                    batch_id=req.batch_id, side=FindingSide.CASH,
                    entry_id=c.id, portfolio_id=c.portfolio_id,
                    finding_type=FindingType.UNMATCHED, finding_reason="Unmatched via Dissolve",
                    created_by=actor.name or actor.id, created_at=now_dc,
                    Modified_by=actor.name or actor.id, Modified_at=now_dc
                )
                db.add(f_cash)
                db.flush()
                db.add(CAP_recon_findings_trail(
                    CAP_recon_finding_ID=f_cash.id, batch_id=req.batch_id,
                    side=f_cash.side, entry_id=f_cash.entry_id,
                    portfolio_id=f_cash.portfolio_id, finding_type=f_cash.finding_type,
                    finding_reason=f_cash.finding_reason, created_by=f_cash.created_by,
                    created_at=now_dc, Modified_by=actor.name or actor.id,
                    Modified_at=now_dc, Action="CREATED"
                ))

    except Exception as e:
        logger.error(f"Error dissolving CAP split: {e}")
        db.rollback()
        raise HTTPException(500, f"Failed to dissolve split: {str(e)}")

    # Audit Log
    log = AuditLog(
        entity="ReconMatch",
        entity_id=req.match_id,
        action="DISSOLVE_MATCH",
        actor=actor.name or actor.id,
        payload={
            "type": "CASH_VS_AP",
            "batch_id": req.batch_id
        }
    )
    db.add(log)

    db.commit()
    return {"message": "Split Match Dissolved Successfully"}
