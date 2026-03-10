from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import os
import logging
from pathlib import Path
from app.ingestion.parsers import BankTxtParser, BrokerCsvParser
from app.database import get_db, SessionLocal
from app.models import (
    BB_Recon_Files, BB_staging_bank_entries, BB_staging_broker_entries, 
    SourceEnum, AuditLog, ProcessingStatus
)
from app.core.upload import SecureUpload
from app.core.security import get_api_key, Actor
from app.core.background_tasks import get_background_processor
from fastapi import Security

logger = logging.getLogger(__name__)
router = APIRouter()


def process_file_async(
    file_id: int,
    file_path: str,
    source: SourceEnum,
    actor_name: str
):
    """
    Background task to process uploaded file.
    Runs virus scan, parsing, and database insertion.
    """
    db = SessionLocal()
    uploader = SecureUpload()
    
    try:
        logger.info(f"Starting async processing for file_id={file_id}")
        
        # Update status to PROCESSING
        recon_file = db.query(BB_Recon_Files).filter(BB_Recon_Files.id == file_id).first()
        if not recon_file:
            raise Exception(f"File record {file_id} not found")
        
        recon_file.processing_status = ProcessingStatus.PROCESSING
        db.commit()
        
        # 1. Virus Scan
        try:
            uploader.scan_for_viruses(Path(file_path), skip_scan=False)
        except HTTPException as e:
            if "Malicious file detected" in str(e.detail):
                recon_file.processing_status = ProcessingStatus.INFECTED
                recon_file.processing_error = "Virus detected in file"
                db.commit()
                # Delete infected file
                if os.path.exists(file_path):
                    os.remove(file_path)
                return
            raise
        
        # 2. Parse file
        if source == SourceEnum.BANK:
            parser = BankTxtParser()
        else:
            parser = BrokerCsvParser()
        
        entries = parser.parse(Path(file_path).read_bytes())
        
        if not entries:
            recon_file.processing_status = ProcessingStatus.FAILED
            recon_file.processing_error = "No valid transactions found in file"
            db.commit()
            return
        
        # 3. Save entries to database
        if source == SourceEnum.BANK:
            db_entries = [
                BB_staging_bank_entries(
                    file_id=file_id,
                    value_date=e['value_date'],
                    reference_no=e['reference_no'],
                    portfolio_id=e.get('portfolio_id'),
                    amount_signed=e['amount_signed'],
                    type_raw=e['type_raw'],
                    validation_error=e['validation_error']
                )
                for e in entries
            ]
        else:
            db_entries = [
                BB_staging_broker_entries(
                    file_id=file_id,
                    value_date=e['value_date'],
                    reference_no=e['reference_no'],
                    portfolio_id=e.get('portfolio_id'),
                    amount_signed=e['amount_signed'],
                    type_raw=e['type_raw'],
                    validation_error=e['validation_error']
                )
                for e in entries
            ]
        
        # Use bulk_insert_mappings for better performance
        if source == SourceEnum.BANK:
            db.bulk_insert_mappings(BB_staging_bank_entries, [
                {
                    'file_id': file_id,
                    'value_date': e['value_date'],
                    'reference_no': e['reference_no'],
                    'portfolio_id': e.get('portfolio_id'),
                    'amount_signed': e['amount_signed'],
                    'type_raw': e['type_raw'],
                    'validation_error': e['validation_error']
                }
                for e in entries
            ])
        else:
            db.bulk_insert_mappings(BB_staging_broker_entries, [
                {
                    'file_id': file_id,
                    'value_date': e['value_date'],
                    'reference_no': e['reference_no'],
                    'portfolio_id': e.get('portfolio_id'),
                    'amount_signed': e['amount_signed'],
                    'type_raw': e['type_raw'],
                    'validation_error': e['validation_error']
                }
                for e in entries
            ])
        
        db.commit()
        
        # 4. Update file record as completed
        recon_file.processing_status = ProcessingStatus.COMPLETED
        recon_file.transaction_count = len(entries)
        db.commit()
        
        # 5. Audit Log
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
        
        logger.info(f"Completed async processing for file_id={file_id}, {len(entries)} entries")
        
    except Exception as e:
        logger.error(f"Error processing file {file_id}: {e}", exc_info=True)
        try:
            recon_file = db.query(BB_Recon_Files).filter(BB_Recon_Files.id == file_id).first()
            if recon_file:
                recon_file.processing_status = ProcessingStatus.FAILED
                recon_file.processing_error = str(e)
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update error status: {db_error}")
        raise
    finally:
        db.close()


@router.post("/ingest/bank")
async def ingest_bank(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key)
):
    """
    Uploads and parses Bank Statement TXT file.
    Optimized for performance with connection pooling and efficient parsing.
    """
    try:
        uploader = SecureUpload()
        
        # 1. Secure Stream to Disk & Size Check (optimized with 64KB chunks)
        temp_path, file_hash, file_size = await uploader.save_upload_to_tmp(file)
        
        # Check for Duplicate Filename
        existing_name = db.query(BB_Recon_Files).filter(
            BB_Recon_Files.file_name == file.filename,
            BB_Recon_Files.source == SourceEnum.BANK
        ).first()

        # We will move the file validation and parsing to the background task
        # But we need to save the file first.
        
        # Move to Immutable Dir immediately to have a path for background task
        final_path = uploader.move_to_upload_dir(temp_path, f"{file_hash}_{file.filename}")
        storage_uri = str(final_path)

        if existing_name:
             # If exists, we might want to error out OR allow re-upload? 
             # Existing logic errored out.
             if os.path.exists(storage_uri):
                 os.remove(storage_uri)
             raise HTTPException(status_code=409, detail=f"File with name '{file.filename}' already exists.")

        # Save File Record with PROCESSING status
        recon_file = BB_Recon_Files(
            source=SourceEnum.BANK,
            file_name=file.filename,
            file_checksum=f"{file_hash}_{file.filename}",
            gcs_path=storage_uri,
            mime_type="text/plain", # We can update this in background or guess now
            file_size_bytes=file_size,
            loaded_by=actor.name if actor.name else actor.id,
            processing_status=ProcessingStatus.PROCESSING,
            transaction_count=0 
        )
        db.add(recon_file)
        db.commit()
        db.refresh(recon_file)

        # Add Background Task
        # Note: process_file_async is defined above in the file
        background_tasks.add_task(
            process_file_async,
            recon_file.id,
            storage_uri,
            SourceEnum.BANK,
            actor.name if actor.name else actor.id
        )
        
        return {
            "message": "Bank Statement Uploaded. Processing in background.",
            "file_id": recon_file.id,
            "status": "PROCESSING"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.post("/ingest/broker")
async def ingest_broker(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key)
):
    """
    Uploads and parses Broker CSV file.
    Optimized for performance with connection pooling and efficient parsing.
    """
    try:
        uploader = SecureUpload()
        
        # 1. Secure Stream to Disk & Size Check (optimized with 64KB chunks)
        temp_path, file_hash, file_size = await uploader.save_upload_to_tmp(file)
        
        # Check for Duplicate Filename
        existing_name = db.query(BB_Recon_Files).filter(
            BB_Recon_Files.file_name == file.filename,
            BB_Recon_Files.source == SourceEnum.BROKER
        ).first()

        # Move to Immutable Dir
        final_path = uploader.move_to_upload_dir(temp_path, f"{file_hash}_{file.filename}")
        storage_uri = str(final_path)

        if existing_name:
             if os.path.exists(storage_uri):
                 os.remove(storage_uri)
             raise HTTPException(status_code=409, detail=f"File with name '{file.filename}' already exists.")

        # Save File Record with PROCESSING status
        recon_file = BB_Recon_Files(
            source=SourceEnum.BROKER,
            file_name=file.filename,
            file_checksum=f"{file_hash}_{file.filename}",
            gcs_path=storage_uri,
            mime_type="text/csv", 
            file_size_bytes=file_size,
            loaded_by=actor.name if actor.name else actor.id,
            processing_status=ProcessingStatus.PROCESSING,
            transaction_count=0
        )
        db.add(recon_file)
        db.commit()
        db.refresh(recon_file)

        # Add Background Task
        background_tasks.add_task(
            process_file_async,
            recon_file.id,
            storage_uri,
            SourceEnum.BROKER,
            actor.name if actor.name else actor.id
        )
        
        return {
            "message": "Broker Statement Uploaded. Processing in background.",
            "file_id": recon_file.id,
            "status": "PROCESSING"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.get("/ingest/status/{file_id}")
async def get_upload_status(
    file_id: int,
    db: Session = Depends(get_db),
    actor: Actor = Security(get_api_key)
):
    """
    Get the processing status of an uploaded file.
    """
    recon_file = db.query(BB_Recon_Files).filter(BB_Recon_Files.id == file_id).first()
    
    if not recon_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    response = {
        "file_id": recon_file.id,
        "file_name": recon_file.file_name,
        "source": recon_file.source.value,
        "status": recon_file.processing_status.value,
        "transaction_count": recon_file.transaction_count,
        "loaded_at": recon_file.loaded_at.isoformat() if recon_file.loaded_at else None
    }
    
    if recon_file.processing_status == ProcessingStatus.FAILED or recon_file.processing_status == ProcessingStatus.INFECTED:
        response["error"] = recon_file.processing_error
    
    # If completed, fetch preview data
    if recon_file.processing_status == ProcessingStatus.COMPLETED:
        if recon_file.source == SourceEnum.BANK:
            entries = db.query(BB_staging_bank_entries).filter(
                BB_staging_bank_entries.file_id == file_id
            ).limit(100).all()
        else:
            entries = db.query(BB_staging_broker_entries).filter(
                BB_staging_broker_entries.file_id == file_id
            ).limit(100).all()
        
        preview_data = []
        for e in entries:
            amt = float(e.amount_signed)
            preview_data.append({
                "Date": e.value_date.isoformat() if e.value_date else None,
                "Reference": e.reference_no,
                "Description": e.type_raw,
                "Debit": abs(amt) if amt < 0 else 0.0,
                "Credit": amt if amt > 0 else 0.0,
                "Balance": 0.0,
                "validation_error": e.validation_error
            })
        
        response["transactions"] = preview_data
    
    return response
