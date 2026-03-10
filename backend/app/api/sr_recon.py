"""
FastAPI Router — Stock Position Reconciliation (sr_recon.py)

Endpoints:
  POST /sr-recon/ingest?source=STOCK_SUMMARY|TRANSACTION_HISTORY
  GET  /sr-recon/ingest/status/{file_id}
  POST /sr-recon/run
  GET  /sr-recon/latest
  GET  /sr-recon/status/{batch_id}
  POST /sr-recon/match/break
  POST /sr-recon/finding/link
"""

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Security, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_api_key, Actor
from app.core.upload import SecureUpload
from app.database import SessionLocal, get_db
from app.engine.sr_core import StockPositionReconEngine
from app.ingestion.parsers import StockSummaryCsvParser, TransHistoryCsvParser
from app.models import (
    AuditLog,
    BatchStatus,
    FindingType,
    MatchKind,
    ProcessingStatus,
    SR_Recon_Files,
    SR_SourceEnum,
    SR_recon_batches,
    SR_recon_findings,
    SR_recon_findings_trail,
    SR_recon_matches,
    SR_recon_matches_trail,
    SR_staging_StockSummary_entries,
    SR_staging_TransHistory_entries,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BACKGROUND PROCESSING
# ---------------------------------------------------------------------------

def _process_sr_file_async(file_id: int, file_path: str, source: SR_SourceEnum, actor_name: str):
    db = SessionLocal()
    try:
        recon_file = db.query(SR_Recon_Files).filter(SR_Recon_Files.id == file_id).first()
        if not recon_file:
            return

        recon_file.processing_status = ProcessingStatus.PROCESSING
        db.commit()

        raw = Path(file_path).read_bytes()

        if source == SR_SourceEnum.STOCK_SUMMARY:
            parser = StockSummaryCsvParser()
            entries_data = parser.parse(raw)
            db_entries = [
                SR_staging_StockSummary_entries(
                    file_id=file_id,
                    portfolio_id=e["portfolio_id"] or None,
                    symbol=e["symbol"] or None,
                    stock_name=e["stock_name"] or None,
                    qty=e["qty"],
                    validation_error=e["validation_error"],
                )
                for e in entries_data
            ]
        else:  # TRANSACTION_HISTORY
            parser = TransHistoryCsvParser()
            entries_data = parser.parse(raw)
            db_entries = [
                SR_staging_TransHistory_entries(
                    file_id=file_id,
                    portfolio_id=e["portfolio_id"] or None,
                    scrip=e["scrip"] or None,
                    transaction_date=e["transaction_date"],
                    balance_after_transaction=e["balance_after_transaction"],
                    validation_error=e["validation_error"],
                )
                for e in entries_data
            ]

        if not db_entries:
            recon_file.processing_status = ProcessingStatus.FAILED
            recon_file.processing_error = "No valid rows found in CSV"
            db.commit()
            return

        db.bulk_save_objects(db_entries)
        recon_file.processing_status = ProcessingStatus.COMPLETED
        recon_file.transaction_count = len(db_entries)
        db.commit()

        # Audit
        log = AuditLog(
            entity="SR_Recon_Files",
            entity_id=str(file_id),
            action="FILE_UPLOAD",
            actor=actor_name,
            payload={"source": source.value, "rows": len(db_entries)},
        )
        db.add(log)
        db.commit()

    except Exception as exc:
        logger.exception("SR file processing failed: %s", exc)
        try:
            recon_file = db.query(SR_Recon_Files).filter(SR_Recon_Files.id == file_id).first()
            if recon_file:
                recon_file.processing_status = ProcessingStatus.FAILED
                recon_file.processing_error = str(exc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ---------------------------------------------------------------------------
# INGEST
# ---------------------------------------------------------------------------

@router.post("/sr-recon/ingest")
async def ingest_sr_file(
    background_tasks: BackgroundTasks,
    source: SR_SourceEnum,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key),
):
    # Strict CSV validation
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    uploader = SecureUpload()
    temp_path, file_hash, file_size = await uploader.save_upload_to_tmp(file)

    checksum_key = f"{file_hash}_{file.filename}"
    existing = db.query(SR_Recon_Files).filter(SR_Recon_Files.file_checksum == checksum_key).first()
    if existing:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=409, detail="File already uploaded")

    final_path = uploader.move_to_upload_dir(temp_path, checksum_key)

    recon_file = SR_Recon_Files(
        source=source,
        file_name=file.filename,
        file_checksum=checksum_key,
        gcs_path=str(final_path),
        mime_type="text/csv",
        file_size_bytes=file_size,
        loaded_by=actor.name or actor.id,
        processing_status=ProcessingStatus.PROCESSING,
        transaction_count=0,
    )
    db.add(recon_file)
    db.commit()
    db.refresh(recon_file)

    background_tasks.add_task(
        _process_sr_file_async,
        recon_file.id,
        str(final_path),
        source,
        actor.name or actor.id,
    )

    return {"message": "File uploaded", "file_id": recon_file.id, "source": source.value}


@router.get("/sr-recon/ingest/status/{file_id}")
def get_sr_ingest_status(file_id: int, db: Session = Depends(get_db)):
    f = db.query(SR_Recon_Files).filter(SR_Recon_Files.id == file_id).first()
    if not f:
        raise HTTPException(404, "File not found")
    return {
        "file_id": f.id,
        "source": f.source.value,
        "status": f.processing_status.value,
        "error": f.processing_error,
        "count": f.transaction_count,
    }


# ---------------------------------------------------------------------------
# RUN RECON
# ---------------------------------------------------------------------------

class RunSrReconRequest(BaseModel):
    summary_file_id: int
    history_file_id: int


@router.post("/sr-recon/run")
def run_sr_recon(
    req: RunSrReconRequest,
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key),
):
    # Ensure files exist and are processed
    ss_file = db.query(SR_Recon_Files).filter(SR_Recon_Files.id == req.summary_file_id).first()
    th_file = db.query(SR_Recon_Files).filter(SR_Recon_Files.id == req.history_file_id).first()
    if not ss_file or not th_file:
        raise HTTPException(404, "One or both files not found")
    if ss_file.processing_status != ProcessingStatus.COMPLETED:
        raise HTTPException(400, "Stock Summary file is still processing or failed")
    if th_file.processing_status != ProcessingStatus.COMPLETED:
        raise HTTPException(400, "Transaction History file is still processing or failed")

    engine = StockPositionReconEngine(db)
    try:
        batch_id = engine.run_batch(
            summary_file_id=req.summary_file_id,
            history_file_id=req.history_file_id,
            actor_id=actor.name or actor.id,
        )
        log = AuditLog(
            entity="SR_recon_batches",
            entity_id=str(batch_id),
            action="SR_AUTO_RECON_RUN",
            actor=actor.name or actor.id,
            payload={
                "summary_file_id": req.summary_file_id,
                "history_file_id": req.history_file_id,
            },
        )
        db.add(log)
        db.commit()
        return _build_sr_response(batch_id, db)
    except Exception as exc:
        logger.exception("SR recon run failed: %s", exc)
        raise HTTPException(500, str(exc))


# ---------------------------------------------------------------------------
# RESPONSE BUILDER
# ---------------------------------------------------------------------------

def _build_sr_response(batch_id: int, db: Session):
    batch = db.query(SR_recon_batches).filter(SR_recon_batches.id == batch_id).first()
    if not batch:
        return {}

    # --- Active matches (exclude BREAK) ---
    matches = db.query(SR_recon_matches).filter(SR_recon_matches.batch_id == batch_id).all()

    subq_m = (
        db.query(
            SR_recon_matches_trail.SR_recon_match_ID,
            SR_recon_matches_trail.Action,
            func.row_number()
            .over(
                partition_by=SR_recon_matches_trail.SR_recon_match_ID,
                order_by=SR_recon_matches_trail.id.desc(),
            )
            .label("rn"),
        )
        .filter(SR_recon_matches_trail.batch_id == batch_id)
        .subquery()
    )
    latest_match_actions = {
        r[0]: r[1]
        for r in db.query(subq_m.c.SR_recon_match_ID, subq_m.c.Action)
        .filter(subq_m.c.rn == 1)
        .all()
    }
    broken_ids = {mid for mid, act in latest_match_actions.items() if act == "BREAK"}
    active_matches = [m for m in matches if m.id not in broken_ids]

    # --- Active findings (both open and resolved) ---
    findings = db.query(SR_recon_findings).filter(SR_recon_findings.batch_id == batch_id).all()

    subq_f = (
        db.query(
            SR_recon_findings_trail.SR_recon_finding_ID,
            SR_recon_findings_trail.Action,
            SR_recon_findings_trail.finding_reason,
            func.row_number()
            .over(
                partition_by=SR_recon_findings_trail.SR_recon_finding_ID,
                order_by=SR_recon_findings_trail.id.desc(),
            )
            .label("rn"),
        )
        .filter(SR_recon_findings_trail.batch_id == batch_id)
        .subquery()
    )
    # Map: finding_id -> {"action": ..., "reason": ...} for latest trail entry
    finding_trail_latest = {
        r[0]: {"action": r[1], "reason": r[2]}
        for r in db.query(
            subq_f.c.SR_recon_finding_ID,
            subq_f.c.Action,
            subq_f.c.finding_reason,
        )
        .filter(subq_f.c.rn == 1)
        .all()
    }
    resolved_finding_ids = {
        fid for fid, data in finding_trail_latest.items()
        if data["action"] in ("LINKED", "RESOLVED")
    }
    active_findings = [f for f in findings if f.id not in resolved_finding_ids]
    # Resolved/linked findings → show in Matched tab with manual reason
    resolved_findings = [f for f in findings if f.id in resolved_finding_ids]

    # --- Fetch staging entries ---
    ss_map = {
        e.id: e
        for e in db.query(SR_staging_StockSummary_entries)
        .filter(SR_staging_StockSummary_entries.file_id == batch.summary_file_id)
        .all()
    }
    th_map = {
        e.id: e
        for e in db.query(SR_staging_TransHistory_entries)
        .filter(SR_staging_TransHistory_entries.file_id == batch.history_file_id)
        .all()
    }

    # --- Build unified row list ---
    rows = []

    consumed_ss = set()
    consumed_th = set()

    for m in active_matches:
        ss = ss_map.get(m.summary_entry_id)
        th = th_map.get(m.history_entry_id)
        match_action = latest_match_actions.get(m.id, "")
        rows.append(
            _fmt_row(
                match_id=m.id,
                match_uid=m.match_id,
                portfolio_id=m.portfolio_id,
                symbol=m.symbol,
                scrip=m.scrip,
                stock_name=ss.stock_name if ss else None,
                ss_qty=float(ss.qty) if (ss and ss.qty is not None) else None,
                th_balance=float(th.balance_after_transaction) if (th and th.balance_after_transaction is not None) else None,
                status="MATCHED",
                match_kind=m.match_kind.value,
                match_action=match_action,
                reason=m.reason,
                ss_entry_id=m.summary_entry_id,
                th_entry_id=m.history_entry_id,
                finding_id=None,
            )
        )
        if m.summary_entry_id:
            consumed_ss.add(m.summary_entry_id)
        if m.history_entry_id:
            consumed_th.add(m.history_entry_id)

    for f in active_findings:
        if f.side == "STOCK_SUMMARY":
            ss = ss_map.get(f.entry_id)
            rows.append(
                _fmt_row(
                    match_id=None,
                    match_uid=None,
                    portfolio_id=f.portfolio_id,
                    symbol=f.symbol_or_scrip,
                    scrip=None,
                    stock_name=ss.stock_name if ss else None,
                    ss_qty=float(ss.qty) if (ss and ss.qty is not None) else None,
                    th_balance=None,
                    status=f.finding_type.value,
                    match_kind=None,
                    match_action=None,
                    reason=f.finding_reason,
                    ss_entry_id=f.entry_id,
                    th_entry_id=None,
                    finding_id=f.id,
                )
            )
        else:  # TRANSACTION_HISTORY
            th = th_map.get(f.entry_id)
            rows.append(
                _fmt_row(
                    match_id=None,
                    match_uid=None,
                    portfolio_id=f.portfolio_id,
                    symbol=None,
                    scrip=f.symbol_or_scrip,
                    stock_name=None,
                    ss_qty=None,
                    th_balance=float(th.balance_after_transaction) if (th and th.balance_after_transaction is not None) else None,
                    status=f.finding_type.value,
                    match_kind=None,
                    match_action=None,
                    reason=f.finding_reason,
                    ss_entry_id=None,
                    th_entry_id=f.entry_id,
                    finding_id=f.id,
                )
            )

    # --- Resolved/linked findings → show as MATCHED rows ---
    for f in resolved_findings:
        trail_data = finding_trail_latest.get(f.id, {})
        link_reason = trail_data.get("reason") or f.finding_reason
        link_action = trail_data.get("action", "RESOLVED")
        if f.side == "STOCK_SUMMARY":
            ss = ss_map.get(f.entry_id)
            rows.append(
                _fmt_row(
                    match_id=None,
                    match_uid=None,
                    portfolio_id=f.portfolio_id,
                    symbol=f.symbol_or_scrip,
                    scrip=None,
                    stock_name=ss.stock_name if ss else None,
                    ss_qty=float(ss.qty) if (ss and ss.qty is not None) else None,
                    th_balance=None,
                    status="MATCHED",
                    match_kind="MANUAL",
                    match_action=link_action,
                    reason=link_reason,
                    ss_entry_id=f.entry_id,
                    th_entry_id=None,
                    finding_id=f.id,
                )
            )
        else:  # TRANSACTION_HISTORY
            th = th_map.get(f.entry_id)
            rows.append(
                _fmt_row(
                    match_id=None,
                    match_uid=None,
                    portfolio_id=f.portfolio_id,
                    symbol=None,
                    scrip=f.symbol_or_scrip,
                    stock_name=None,
                    ss_qty=None,
                    th_balance=float(th.balance_after_transaction) if (th and th.balance_after_transaction is not None) else None,
                    status="MATCHED",
                    match_kind="MANUAL",
                    match_action=link_action,
                    reason=link_reason,
                    ss_entry_id=None,
                    th_entry_id=f.entry_id,
                    finding_id=f.id,
                )
            )

    summary = {
        "total_matches": len(active_matches) + len(resolved_findings),
        "auto_match_count": sum(1 for m in active_matches if m.match_kind == MatchKind.AUTO),
        "manual_match_count": sum(1 for m in active_matches if m.match_kind == MatchKind.MANUAL) + len(resolved_findings),
        "unmatched_count": sum(1 for r in rows if r["status"] == "UNMATCHED"),
        "exception_count": sum(1 for r in rows if r["status"] == "EXCEPTION"),
    }

    return {
        "batch_id": batch.id,
        "summary_file_id": batch.summary_file_id,
        "history_file_id": batch.history_file_id,
        "rows": rows,
        "summary": summary,
    }


def _fmt_row(
    *,
    match_id,
    match_uid,
    portfolio_id,
    symbol,
    scrip,
    stock_name,
    ss_qty,
    th_balance,
    status,
    match_kind,
    match_action,
    reason,
    ss_entry_id,
    th_entry_id,
    finding_id,
):
    return {
        "match_id": match_id,
        "match_uid": match_uid,
        "finding_id": finding_id,
        "portfolio_id": portfolio_id,
        "symbol": symbol,
        "scrip": scrip,
        "stock_name": stock_name,
        "ss_qty": ss_qty,
        "th_balance": th_balance,
        "status": status,
        "match_kind": match_kind,
        "match_action": match_action,
        "reason": reason,
        "ss_entry_id": ss_entry_id,
        "th_entry_id": th_entry_id,
    }


# ---------------------------------------------------------------------------
# LATEST
# ---------------------------------------------------------------------------

@router.get("/sr-recon/latest")
def get_latest_sr_recon(
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key),
):
    batches = db.query(SR_recon_batches).order_by(SR_recon_batches.id.desc()).all()
    if not batches:
        return {"message": "No history"}

    combined_rows = []
    total_summary = {
        "total_matches": 0,
        "auto_match_count": 0,
        "manual_match_count": 0,
        "unmatched_count": 0,
        "exception_count": 0,
    }

    for b in batches:
        data = _build_sr_response(b.id, db)
        if not data:
            continue
        combined_rows.extend(data.get("rows", []))
        s = data.get("summary", {})
        for k in total_summary:
            total_summary[k] += s.get(k, 0)

    latest = batches[0]
    return {
        "batch_id": latest.id,
        "summary_file_id": latest.summary_file_id,
        "history_file_id": latest.history_file_id,
        "rows": combined_rows,
        "summary": total_summary,
    }


@router.get("/sr-recon/status/{batch_id}")
def get_sr_recon_status(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(SR_recon_batches).filter(SR_recon_batches.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")
    return {
        "id": batch.id,
        "status": batch.status.value,
        "started_at": batch.started_at,
        "completed_at": batch.completed_at,
    }


# ---------------------------------------------------------------------------
# BREAK (auto-match → unmatched)
# ---------------------------------------------------------------------------

class BreakMatchRequest(BaseModel):
    match_id: int
    reason: str


@router.post("/sr-recon/match/break")
def break_sr_match(
    req: BreakMatchRequest,
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key),
):
    if not req.reason or not req.reason.strip():
        raise HTTPException(400, "A reason is required to break a match")

    match = db.query(SR_recon_matches).filter(SR_recon_matches.id == req.match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")

    now = datetime.utcnow()
    trail = SR_recon_matches_trail(
        SR_recon_match_ID=match.id,
        batch_id=match.batch_id,
        summary_entry_id=match.summary_entry_id,
        history_entry_id=match.history_entry_id,
        portfolio_id=match.portfolio_id,
        symbol=match.symbol,
        scrip=match.scrip,
        match_kind=match.match_kind,
        match_id=match.match_id,
        reason=req.reason,
        created_by=match.created_by,
        created_at=match.created_at,
        Modified_by=actor.name or actor.id,
        Modified_at=now,
        Action="BREAK",
    )
    db.add(trail)

    # Re-create UNMATCHED findings for both sides
    if match.summary_entry_id:
        ss = db.query(SR_staging_StockSummary_entries).filter(
            SR_staging_StockSummary_entries.id == match.summary_entry_id
        ).first()
        f = SR_recon_findings(
            batch_id=match.batch_id,
            side="STOCK_SUMMARY",
            entry_id=match.summary_entry_id,
            portfolio_id=match.portfolio_id,
            symbol_or_scrip=match.symbol,
            finding_type=FindingType.UNMATCHED,
            finding_reason=req.reason,
            created_at=now,
            created_by=actor.name or actor.id,
        )
        db.add(f)
        db.flush()
        db.add(SR_recon_findings_trail(
            SR_recon_finding_ID=f.id,
            batch_id=match.batch_id,
            side="STOCK_SUMMARY",
            entry_id=match.summary_entry_id,
            portfolio_id=match.portfolio_id,
            symbol_or_scrip=match.symbol,
            finding_type=FindingType.UNMATCHED,
            finding_reason=f.finding_reason,
            created_at=now,
            created_by=actor.name or actor.id,
            Action="CREATE",
        ))

    if match.history_entry_id:
        f2 = SR_recon_findings(
            batch_id=match.batch_id,
            side="TRANSACTION_HISTORY",
            entry_id=match.history_entry_id,
            portfolio_id=match.portfolio_id,
            symbol_or_scrip=match.scrip,
            finding_type=FindingType.UNMATCHED,
            finding_reason=req.reason,
            created_at=now,
            created_by=actor.name or actor.id,
        )
        db.add(f2)
        db.flush()
        db.add(SR_recon_findings_trail(
            SR_recon_finding_ID=f2.id,
            batch_id=match.batch_id,
            side="TRANSACTION_HISTORY",
            entry_id=match.history_entry_id,
            portfolio_id=match.portfolio_id,
            symbol_or_scrip=match.scrip,
            finding_type=FindingType.UNMATCHED,
            finding_reason=f2.finding_reason,
            created_at=now,
            created_by=actor.name or actor.id,
            Action="CREATE",
        ))

    # Audit log
    db.add(AuditLog(
        entity="SR_recon_matches",
        entity_id=str(match.id),
        action="SR_MATCH_BREAK",
        actor=actor.name or actor.id,
        payload={"reason": req.reason},
    ))
    db.commit()

    return {"message": "Match broken", "match_id": req.match_id}


# ---------------------------------------------------------------------------
# BREAK RESOLVED FINDING (finding → back to unmatched)
# ---------------------------------------------------------------------------

class BreakFindingRequest(BaseModel):
    finding_id: int
    reason: str


@router.post("/sr-recon/finding/break")
def break_resolved_finding(
    req: BreakFindingRequest,
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key),
):
    if not req.reason or not req.reason.strip():
        raise HTTPException(400, "A reason is required to break a resolved finding")

    finding = db.query(SR_recon_findings).filter(SR_recon_findings.id == req.finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    now = datetime.utcnow()

    # Add UNRESOLVED trail — this removes it from resolved_finding_ids in _build_sr_response
    db.add(SR_recon_findings_trail(
        SR_recon_finding_ID=finding.id,
        batch_id=finding.batch_id,
        side=finding.side,
        entry_id=finding.entry_id,
        portfolio_id=finding.portfolio_id,
        symbol_or_scrip=finding.symbol_or_scrip,
        finding_type=finding.finding_type,
        finding_reason=f"Broken by {actor.name or actor.id}: {req.reason}",
        created_at=now,
        created_by=actor.name or actor.id,
        Modified_by=actor.name or actor.id,
        Modified_at=now,
        Action="UNRESOLVED",
    ))

    db.add(AuditLog(
        entity="SR_recon_findings",
        entity_id=str(finding.id),
        action="SR_FINDING_UNRESOLVE",
        actor=actor.name or actor.id,
        payload={"finding_id": finding.id, "reason": req.reason},
    ))
    db.commit()

    return {"message": "Finding unresolved", "finding_id": finding.id}



class LinkFindingRequest(BaseModel):
    batch_id: int
    ss_entry_id: Optional[int] = None
    th_entry_id: Optional[int] = None
    reason: str


@router.post("/sr-recon/finding/link")
def link_sr_finding(
    req: LinkFindingRequest,
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key),
):
    if not req.reason or not req.reason.strip():
        raise HTTPException(400, "A reason is required to link entries")
    if not req.ss_entry_id and not req.th_entry_id:
        raise HTTPException(400, "At least one entry ID (ss_entry_id or th_entry_id) is required")

    batch = db.query(SR_recon_batches).filter(SR_recon_batches.id == req.batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")

    now = datetime.utcnow()

    # ── Dual-sided: create a full manual match ────────────────────────────────
    if req.ss_entry_id and req.th_entry_id:
        ss = db.query(SR_staging_StockSummary_entries).filter(
            SR_staging_StockSummary_entries.id == req.ss_entry_id
        ).first()
        th = db.query(SR_staging_TransHistory_entries).filter(
            SR_staging_TransHistory_entries.id == req.th_entry_id
        ).first()
        if not ss or not th:
            raise HTTPException(404, "One or both staging entries not found")

        mid = f"SR-MAN-{batch.id}-{uuid.uuid4().hex[:8].upper()}"
        match = SR_recon_matches(
            batch_id=batch.id,
            summary_entry_id=ss.id,
            history_entry_id=th.id,
            portfolio_id=ss.portfolio_id,
            symbol=ss.symbol,
            scrip=th.scrip,
            match_kind=MatchKind.MANUAL,
            match_id=mid,
            reason=req.reason,
            created_by=actor.name or actor.id,
            created_at=now,
            Modified_by=actor.name or actor.id,
            Modified_at=now,
        )
        db.add(match)
        db.flush()

        db.add(SR_recon_matches_trail(
            SR_recon_match_ID=match.id,
            batch_id=batch.id,
            summary_entry_id=ss.id,
            history_entry_id=th.id,
            portfolio_id=ss.portfolio_id,
            symbol=ss.symbol,
            scrip=th.scrip,
            match_kind=MatchKind.MANUAL,
            match_id=mid,
            reason=req.reason,
            created_by=actor.name or actor.id,
            created_at=now,
            Modified_by=actor.name or actor.id,
            Modified_at=now,
            Action="MANUAL_MATCH",
        ))

        # Resolve open findings for both sides
        for side, entry_id in [("STOCK_SUMMARY", ss.id), ("TRANSACTION_HISTORY", th.id)]:
            open_findings = (
                db.query(SR_recon_findings)
                .filter(
                    SR_recon_findings.batch_id == batch.id,
                    SR_recon_findings.side == side,
                    SR_recon_findings.entry_id == entry_id,
                )
                .all()
            )
            for f in open_findings:
                db.add(SR_recon_findings_trail(
                    SR_recon_finding_ID=f.id,
                    batch_id=batch.id,
                    side=f.side,
                    entry_id=f.entry_id,
                    portfolio_id=f.portfolio_id,
                    symbol_or_scrip=f.symbol_or_scrip,
                    finding_type=f.finding_type,
                    finding_reason=f.finding_reason,
                    created_at=now,
                    created_by=actor.name or actor.id,
                    Modified_by=actor.name or actor.id,
                    Modified_at=now,
                    Action="LINKED",
                ))

        db.add(AuditLog(
            entity="SR_recon_matches",
            entity_id=str(match.id),
            action="SR_MANUAL_LINK",
            actor=actor.name or actor.id,
            payload={"ss_entry_id": req.ss_entry_id, "th_entry_id": req.th_entry_id, "reason": req.reason},
        ))
        db.commit()
        return {"message": "Entries linked", "match_id": match.id, "match_uid": mid}

    # ── Single-sided: resolve the finding with a reason only ──────────────────
    side = "STOCK_SUMMARY" if req.ss_entry_id else "TRANSACTION_HISTORY"
    entry_id = req.ss_entry_id or req.th_entry_id

    open_findings = (
        db.query(SR_recon_findings)
        .filter(
            SR_recon_findings.batch_id == batch.id,
            SR_recon_findings.side == side,
            SR_recon_findings.entry_id == entry_id,
        )
        .all()
    )
    if not open_findings:
        raise HTTPException(404, "No open finding found for this entry")

    for f in open_findings:
        db.add(SR_recon_findings_trail(
            SR_recon_finding_ID=f.id,
            batch_id=batch.id,
            side=f.side,
            entry_id=f.entry_id,
            portfolio_id=f.portfolio_id,
            symbol_or_scrip=f.symbol_or_scrip,
            finding_type=f.finding_type,
            finding_reason=req.reason,
            created_at=now,
            created_by=actor.name or actor.id,
            Modified_by=actor.name or actor.id,
            Modified_at=now,
            Action="RESOLVED",
        ))

    db.add(AuditLog(
        entity="SR_recon_findings",
        entity_id=str(open_findings[0].id),
        action="SR_FINDING_RESOLVE",
        actor=actor.name or actor.id,
        payload={"entry_id": entry_id, "side": side, "reason": req.reason},
    ))
    db.commit()
    return {"message": "Finding resolved", "entry_id": entry_id, "side": side}
