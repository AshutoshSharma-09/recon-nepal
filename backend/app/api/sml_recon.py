"""
FastAPI Router — Stock Movement Liquidation Reconciliation (sml_recon.py)

Endpoints:
  POST /sml-recon/ingest?source=STOCK_LIQUIDATION|TRANSACTION_HISTORY
  GET  /sml-recon/ingest/status/{file_id}
  POST /sml-recon/run
  GET  /sml-recon/latest
  POST /sml-recon/match/break
  POST /sml-recon/finding/break
  POST /sml-recon/finding/link
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
from app.engine.sml_core import StockLiquidationReconEngine
from app.ingestion.parsers import StockLiquidationCsvParser, LiqTransHistoryCsvParser
from app.models import (
    AuditLog,
    BatchStatus,
    FindingType,
    MatchKind,
    ProcessingStatus,
    SML_Recon_Files,
    SML_SourceEnum,
    SML_recon_batches,
    SML_recon_findings,
    SML_recon_findings_trail,
    SML_recon_matches,
    SML_recon_matches_trail,
    SML_staging_StockLiquidation_entries,
    SML_staging_TransHistory_entries,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BACKGROUND FILE PROCESSING
# ---------------------------------------------------------------------------

def _process_sml_file_async(file_id: int, file_path: str, source: SML_SourceEnum, actor_name: str):
    db = SessionLocal()
    try:
        recon_file = db.query(SML_Recon_Files).filter(SML_Recon_Files.id == file_id).first()
        if not recon_file:
            return

        recon_file.processing_status = ProcessingStatus.PROCESSING
        db.commit()

        raw = Path(file_path).read_bytes()

        if source == SML_SourceEnum.STOCK_LIQUIDATION:
            parser = StockLiquidationCsvParser()
            entries_data = parser.parse(raw)
            db_entries = [
                SML_staging_StockLiquidation_entries(
                    file_id=file_id,
                    portfolio_id=e["portfolio_id"] or None,
                    scrip=e["scrip"] or None,
                    stock_name=e.get("stock_name") or None,
                    qty=e["qty"],
                    validation_error=e["validation_error"],
                )
                for e in entries_data
            ]
        else:  # TRANSACTION_HISTORY
            parser = LiqTransHistoryCsvParser()
            entries_data = parser.parse(raw)
            db_entries = [
                SML_staging_TransHistory_entries(
                    file_id=file_id,
                    portfolio_id=e["portfolio_id"] or None,
                    scrip=e["scrip"] or None,
                    transaction_date=e["transaction_date"],
                    debit_quantity=e["debit_quantity"],
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
            entity="SML_Recon_Files",
            entity_id=str(file_id),
            action="SML_FILE_UPLOAD",
            actor=actor_name,
            payload={"source": source.value, "rows": len(db_entries)},
        )
        db.add(log)
        db.commit()

    except Exception as exc:
        logger.exception("SML file processing failed: %s", exc)
        try:
            recon_file = db.query(SML_Recon_Files).filter(SML_Recon_Files.id == file_id).first()
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

@router.post("/sml-recon/ingest")
async def ingest_sml_file(
    background_tasks: BackgroundTasks,
    source: SML_SourceEnum,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key),
):
    """Upload a CSV file for Stock Movement Liquidation reconciliation."""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    uploader = SecureUpload()
    temp_path, file_hash, file_size = await uploader.save_upload_to_tmp(file)

    checksum_key = f"{file_hash}_{file.filename}"
    existing = db.query(SML_Recon_Files).filter(SML_Recon_Files.file_checksum == checksum_key).first()
    if existing:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=409, detail="File already uploaded")

    final_path = uploader.move_to_upload_dir(temp_path, checksum_key)

    recon_file = SML_Recon_Files(
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
        _process_sml_file_async,
        recon_file.id,
        str(final_path),
        source,
        actor.name or actor.id,
    )

    return {"message": "File uploaded", "file_id": recon_file.id, "source": source.value}


@router.get("/sml-recon/ingest/status/{file_id}")
def get_sml_ingest_status(file_id: int, db: Session = Depends(get_db)):
    f = db.query(SML_Recon_Files).filter(SML_Recon_Files.id == file_id).first()
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

class RunSmlReconRequest(BaseModel):
    liquidation_file_id: int
    history_file_id: int


@router.post("/sml-recon/run")
def run_sml_recon(
    req: RunSmlReconRequest,
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key),
):
    """Run the Stock Movement Liquidation reconciliation engine."""
    liq_file = db.query(SML_Recon_Files).filter(SML_Recon_Files.id == req.liquidation_file_id).first()
    th_file  = db.query(SML_Recon_Files).filter(SML_Recon_Files.id == req.history_file_id).first()
    if not liq_file or not th_file:
        raise HTTPException(404, "One or both files not found")
    if liq_file.processing_status != ProcessingStatus.COMPLETED:
        raise HTTPException(400, "Stock Liquidation file is still processing or failed")
    if th_file.processing_status != ProcessingStatus.COMPLETED:
        raise HTTPException(400, "Transaction History file is still processing or failed")

    eng = StockLiquidationReconEngine(db)
    try:
        batch_id = eng.run_batch(
            liquidation_file_id=req.liquidation_file_id,
            history_file_id=req.history_file_id,
            actor_id=actor.name or actor.id,
        )
        log = AuditLog(
            entity="SML_recon_batches",
            entity_id=str(batch_id),
            action="SML_AUTO_RECON_RUN",
            actor=actor.name or actor.id,
            payload={
                "liquidation_file_id": req.liquidation_file_id,
                "history_file_id": req.history_file_id,
            },
        )
        db.add(log)
        db.commit()
        return _build_sml_response(batch_id, db)
    except Exception as exc:
        logger.exception("SML recon run failed: %s", exc)
        raise HTTPException(500, str(exc))


# ---------------------------------------------------------------------------
# LATEST BATCH
# ---------------------------------------------------------------------------

@router.get("/sml-recon/latest")
def get_latest_sml_batch(db: Session = Depends(get_db), actor: Actor = Security(get_api_key)):
    """Return results of the most recently completed SML batch."""
    batch = (
        db.query(SML_recon_batches)
        .filter(SML_recon_batches.status == BatchStatus.COMPLETED)
        .order_by(SML_recon_batches.id.desc())
        .first()
    )
    if not batch:
        return {"rows": [], "batch_id": None, "summary": {}}
    return _build_sml_response(batch.id, db)


# ---------------------------------------------------------------------------
# RESPONSE BUILDER
# ---------------------------------------------------------------------------

def _build_sml_response(batch_id: int, db: Session):
    batch = db.query(SML_recon_batches).filter(SML_recon_batches.id == batch_id).first()
    if not batch:
        return {"rows": [], "batch_id": None, "summary": {}}

    # --- Active matches ---
    matches = db.query(SML_recon_matches).filter(SML_recon_matches.batch_id == batch_id).all()

    subq_m = (
        db.query(
            SML_recon_matches_trail.SML_recon_match_ID,
            SML_recon_matches_trail.Action,
            func.row_number()
            .over(
                partition_by=SML_recon_matches_trail.SML_recon_match_ID,
                order_by=SML_recon_matches_trail.id.desc(),
            )
            .label("rn"),
        )
        .filter(SML_recon_matches_trail.batch_id == batch_id)
        .subquery()
    )
    latest_match_actions = {
        r[0]: r[1]
        for r in db.query(subq_m.c.SML_recon_match_ID, subq_m.c.Action)
        .filter(subq_m.c.rn == 1)
        .all()
    }
    broken_ids = {mid for mid, act in latest_match_actions.items() if act == "BREAK"}
    active_matches = [m for m in matches if m.id not in broken_ids]

    # --- Findings ---
    findings = db.query(SML_recon_findings).filter(SML_recon_findings.batch_id == batch_id).all()

    subq_f = (
        db.query(
            SML_recon_findings_trail.SML_recon_finding_ID,
            SML_recon_findings_trail.Action,
            SML_recon_findings_trail.finding_reason,
            func.row_number()
            .over(
                partition_by=SML_recon_findings_trail.SML_recon_finding_ID,
                order_by=SML_recon_findings_trail.id.desc(),
            )
            .label("rn"),
        )
        .filter(SML_recon_findings_trail.batch_id == batch_id)
        .subquery()
    )
    finding_trail_latest = {
        r[0]: {"action": r[1], "reason": r[2]}
        for r in db.query(
            subq_f.c.SML_recon_finding_ID,
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
    active_findings   = [f for f in findings if f.id not in resolved_finding_ids]
    resolved_findings = [f for f in findings if f.id in resolved_finding_ids]

    # --- Build rows ---
    rows = []

    for m in active_matches:
        rows.append(
            _fmt_row(
                match_id=m.id,
                match_uid=m.match_id,
                portfolio_id=m.portfolio_id,
                scrip=m.scrip,
                stock_name=m.stock_name,
                liq_qty_sum=float(m.liq_qty_sum) if m.liq_qty_sum is not None else None,
                th_debit_qty_sum=float(m.th_debit_qty_sum) if m.th_debit_qty_sum is not None else None,
                status="MATCHED",
                match_kind=m.match_kind.value,
                match_action=latest_match_actions.get(m.id, ""),
                reason=m.reason,
                finding_id=None,
                liq_entry_ids=m.liquidation_entry_ids,
                th_entry_ids=m.history_entry_ids,
            )
        )

    for f in active_findings:
        rows.append(
            _fmt_row(
                match_id=None,
                match_uid=None,
                portfolio_id=f.portfolio_id,
                scrip=f.scrip,
                stock_name=f.stock_name,
                liq_qty_sum=float(f.liq_qty_sum) if f.liq_qty_sum is not None else None,
                th_debit_qty_sum=float(f.th_debit_qty_sum) if f.th_debit_qty_sum is not None else None,
                status=f.finding_type.value,
                match_kind=None,
                match_action=None,
                reason=f.finding_reason,
                finding_id=f.id,
                liq_entry_ids=f.entry_ids,
                th_entry_ids=None,
            )
        )

    # Resolved findings appear as MATCHED (manual link)
    for f in resolved_findings:
        trail = finding_trail_latest.get(f.id, {})
        rows.append(
            _fmt_row(
                match_id=None,
                match_uid=None,
                portfolio_id=f.portfolio_id,
                scrip=f.scrip,
                stock_name=f.stock_name,
                liq_qty_sum=float(f.liq_qty_sum) if f.liq_qty_sum is not None else None,
                th_debit_qty_sum=float(f.th_debit_qty_sum) if f.th_debit_qty_sum is not None else None,
                status="MATCHED",
                match_kind="MANUAL",
                match_action=trail.get("action", ""),
                reason=trail.get("reason") or f.finding_reason,
                finding_id=f.id,
                liq_entry_ids=f.entry_ids,
                th_entry_ids=None,
            )
        )

    total     = len(rows)
    matched   = sum(1 for r in rows if r["status"] == "MATCHED")
    unmatched = sum(1 for r in rows if r["status"] == "UNMATCHED")
    exception = sum(1 for r in rows if r["status"] == "EXCEPTION")

    return {
        "batch_id": batch_id,
        "rows": rows,
        "summary": {
            "total": total,
            "matched": matched,
            "unmatched": unmatched,
            "exception": exception,
        },
    }


def _fmt_row(
    *,
    match_id,
    match_uid,
    portfolio_id,
    scrip,
    stock_name,
    liq_qty_sum,
    th_debit_qty_sum,
    status,
    match_kind,
    match_action,
    reason,
    finding_id,
    liq_entry_ids,
    th_entry_ids,
):
    return {
        "match_id":         match_id,
        "match_uid":        match_uid,
        "portfolio_id":     portfolio_id,
        "scrip":            scrip,
        "stock_name":       stock_name,
        "liq_qty_sum":      liq_qty_sum,
        "th_debit_qty_sum": th_debit_qty_sum,
        "status":           status,
        "match_kind":       match_kind,
        "match_action":     match_action,
        "reason":           reason,
        "finding_id":       finding_id,
        "liq_entry_ids":    liq_entry_ids,
        "th_entry_ids":     th_entry_ids,
    }


# ---------------------------------------------------------------------------
# BREAK MATCH
# ---------------------------------------------------------------------------

class BreakMatchRequest(BaseModel):
    match_id: int
    reason: str


@router.post("/sml-recon/match/break")
def break_sml_match(
    req: BreakMatchRequest,
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key),
):
    """Break an auto-matched SML entry. Reason is required."""
    if not req.reason or not req.reason.strip():
        raise HTTPException(400, "A reason is required to break a match")

    match = db.query(SML_recon_matches).filter(SML_recon_matches.id == req.match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")

    now = datetime.utcnow()
    trail = SML_recon_matches_trail(
        SML_recon_match_ID=match.id,
        batch_id=match.batch_id,
        liquidation_entry_ids=match.liquidation_entry_ids,
        history_entry_ids=match.history_entry_ids,
        portfolio_id=match.portfolio_id,
        scrip=match.scrip,
        liq_qty_sum=match.liq_qty_sum,
        th_debit_qty_sum=match.th_debit_qty_sum,
        match_kind=match.match_kind,
        match_id=match.match_id,
        reason=req.reason,
        created_by=actor.name or actor.id,
        created_at=now,
        Modified_by=actor.name or actor.id,
        Modified_at=now,
        Action="BREAK",
    )
    db.add(trail)

    # Create an UNMATCHED finding from the broken match
    liq_entry_id = int(match.liquidation_entry_ids.split(",")[0]) if match.liquidation_entry_ids else None
    finding = SML_recon_findings(
        batch_id=match.batch_id,
        side="STOCK_LIQUIDATION",
        entry_id=liq_entry_id,
        entry_ids=match.liquidation_entry_ids,
        portfolio_id=match.portfolio_id,
        scrip=match.scrip,
        stock_name=match.stock_name,
        liq_qty_sum=match.liq_qty_sum,
        th_debit_qty_sum=match.th_debit_qty_sum,
        finding_type=FindingType.UNMATCHED,
        finding_reason=req.reason,
        created_at=now,
        created_by=actor.name or actor.id,
    )
    db.add(finding)
    db.flush()

    finding_trail = SML_recon_findings_trail(
        SML_recon_finding_ID=finding.id,
        batch_id=finding.batch_id,
        side=finding.side,
        entry_id=finding.entry_id,
        entry_ids=finding.entry_ids,
        portfolio_id=finding.portfolio_id,
        scrip=finding.scrip,
        liq_qty_sum=finding.liq_qty_sum,
        th_debit_qty_sum=finding.th_debit_qty_sum,
        finding_type=finding.finding_type,
        finding_reason=finding.finding_reason,
        created_at=now,
        created_by=actor.name or actor.id,
        Action="CREATE",
    )
    db.add(finding_trail)

    log = AuditLog(
        entity="SML_recon_matches",
        entity_id=str(match.id),
        action="SML_MATCH_BREAK",
        actor=actor.name or actor.id,
        payload={"reason": req.reason},
    )
    db.add(log)
    db.commit()

    return _build_sml_response(match.batch_id, db)


# ---------------------------------------------------------------------------
# BREAK FINDING  (un-resolve a resolved finding)
# ---------------------------------------------------------------------------

class BreakFindingRequest(BaseModel):
    finding_id: int
    reason: str


@router.post("/sml-recon/finding/break")
def break_sml_finding(
    req: BreakFindingRequest,
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key),
):
    """Re-open a previously linked/resolved SML finding."""
    if not req.reason or not req.reason.strip():
        raise HTTPException(400, "A reason is required")

    finding = db.query(SML_recon_findings).filter(SML_recon_findings.id == req.finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    now = datetime.utcnow()
    trail = SML_recon_findings_trail(
        SML_recon_finding_ID=finding.id,
        batch_id=finding.batch_id,
        side=finding.side,
        entry_id=finding.entry_id,
        entry_ids=finding.entry_ids,
        portfolio_id=finding.portfolio_id,
        scrip=finding.scrip,
        liq_qty_sum=finding.liq_qty_sum,
        th_debit_qty_sum=finding.th_debit_qty_sum,
        finding_type=finding.finding_type,
        finding_reason=req.reason,
        created_at=now,
        created_by=actor.name or actor.id,
        Modified_by=actor.name or actor.id,
        Modified_at=now,
        Action="BREAK",
    )
    db.add(trail)

    log = AuditLog(
        entity="SML_recon_findings",
        entity_id=str(finding.id),
        action="SML_FINDING_BREAK",
        actor=actor.name or actor.id,
        payload={"reason": req.reason},
    )
    db.add(log)
    db.commit()

    return _build_sml_response(finding.batch_id, db)


# ---------------------------------------------------------------------------
# LINK FINDING
# ---------------------------------------------------------------------------

class LinkFindingRequest(BaseModel):
    finding_id: int
    reason: str


@router.post("/sml-recon/finding/link")
def link_sml_finding(
    req: LinkFindingRequest,
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key),
):
    """Manually resolve/link an unmatched or exception SML finding. Reason is required."""
    if not req.reason or not req.reason.strip():
        raise HTTPException(400, "A reason is required to link a finding")

    finding = db.query(SML_recon_findings).filter(SML_recon_findings.id == req.finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    now = datetime.utcnow()
    trail = SML_recon_findings_trail(
        SML_recon_finding_ID=finding.id,
        batch_id=finding.batch_id,
        side=finding.side,
        entry_id=finding.entry_id,
        entry_ids=finding.entry_ids,
        portfolio_id=finding.portfolio_id,
        scrip=finding.scrip,
        liq_qty_sum=finding.liq_qty_sum,
        th_debit_qty_sum=finding.th_debit_qty_sum,
        finding_type=finding.finding_type,
        finding_reason=req.reason,
        created_at=now,
        created_by=actor.name or actor.id,
        Modified_by=actor.name or actor.id,
        Modified_at=now,
        Action="LINKED",
    )
    db.add(trail)

    log = AuditLog(
        entity="SML_recon_findings",
        entity_id=str(finding.id),
        action="SML_FINDING_LINK",
        actor=actor.name or actor.id,
        payload={"reason": req.reason},
    )
    db.add(log)
    db.commit()

    return _build_sml_response(finding.batch_id, db)
