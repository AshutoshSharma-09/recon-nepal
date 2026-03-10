from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Enum, JSON, Date, BigInteger, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base

# --- Enums from Specs ---
class SourceEnum(enum.Enum):
    BROKER = "BROKER"
    BANK = "BANK"

class BatchStatus(enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class MatchKind(enum.Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"

class FindingType(enum.Enum):
    EXCEPTION = "EXCEPTION"
    UNMATCHED = "UNMATCHED"
    LINKABLE = "LINKABLE"

class FindingSide(str, enum.Enum):
    BROKER = "BROKER"
    BANK = "BANK"
    CASH = "CASH"
    RECEIVABLE = "RECEIVABLE"
    PAYABLE = "PAYABLE"

# --- 1. Data Ingestion and Source Metadata Framework (Immutable) ---
class ProcessingStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INFECTED = "INFECTED"

class BB_Recon_Files(Base):
    __tablename__ = "BB_Recon_Files"

    id = Column("ID", Integer, primary_key=True, index=True)
    source = Column("Source", Enum(SourceEnum), nullable=False)
    file_name = Column(String, nullable=False)
    file_checksum = Column(String, unique=True, nullable=False)
    gcs_path = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    loaded_by = Column(String, nullable=True)
    loaded_at = Column(DateTime, default=datetime.utcnow)
    
    # Processing status for async uploads
    processing_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING, nullable=False, index=True)
    processing_error = Column(String, nullable=True)
    transaction_count = Column(Integer, nullable=True)

    # Relationships
    broker_batches = relationship("BB_recon_batches", foreign_keys="[BB_recon_batches.broker_file_id]", back_populates="broker_file")
    bank_batches = relationship("BB_recon_batches", foreign_keys="[BB_recon_batches.bank_file_id]", back_populates="bank_file")

# --- 2. Transactional Staging (Mutable for Validation Error) ---
class BB_staging_broker_entries(Base):
    __tablename__ = "BB_staging_broker_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("BB_Recon_Files.ID"), nullable=False)
    
    value_date = Column(Date, nullable=True, index=True)
    reference_no = Column(String, nullable=True, index=True)
    portfolio_id = Column(String, nullable=True, index=True)
    amount_signed = Column(Numeric(18, 2), nullable=False, index=True)
    type_raw = Column(String, nullable=True)
    validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class BB_staging_bank_entries(Base):
    __tablename__ = "BB_staging_bank_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("BB_Recon_Files.ID"), nullable=False)
    
    value_date = Column(Date, nullable=True, index=True)
    reference_no = Column(String, nullable=True, index=True)
    portfolio_id = Column(String, nullable=True, index=True)
    amount_signed = Column(Numeric(18, 2), nullable=False, index=True)
    type_raw = Column(String, nullable=True)
    validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# --- 3. Core Reconciliation Engine (Mutable) ---
class BB_recon_batches(Base):
    __tablename__ = "BB_recon_batches"

    id = Column(Integer, primary_key=True, index=True)
    broker_file_id = Column(Integer, ForeignKey("BB_Recon_Files.ID"), nullable=False)
    bank_file_id = Column(Integer, ForeignKey("BB_Recon_Files.ID"), nullable=False)
    
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(Enum(BatchStatus), default=BatchStatus.RUNNING)

    broker_file = relationship("BB_Recon_Files", foreign_keys=[broker_file_id], back_populates="broker_batches")
    bank_file = relationship("BB_Recon_Files", foreign_keys=[bank_file_id], back_populates="bank_batches")
    
    matches = relationship("BB_recon_matches", back_populates="batch")
    findings = relationship("BB_recon_findings", back_populates="batch")

class BB_recon_matches(Base):
    __tablename__ = "BB_recon_matches"

    id = Column("ID", Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("BB_recon_batches.id"), nullable=False)
    
    broker_entry_id = Column(BigInteger, ForeignKey("BB_staging_broker_entries.id"), nullable=False)
    bank_entry_id = Column(BigInteger, ForeignKey("BB_staging_bank_entries.id"), nullable=False)
    
    # User Request: Foreign Key to BB_staging_bank_entries.portfolio_id
    portfolio_id = Column(String, nullable=True, index=True)
    
    match_kind = Column(Enum(MatchKind), nullable=False, index=True)
    match_id = Column(String, nullable=False, index=True)
    
    canonical_reference = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    batch = relationship("BB_recon_batches", back_populates="matches")

class BB_recon_findings(Base):
    __tablename__ = "BB_recon_findings"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("BB_recon_batches.id"), nullable=False)
    
    side = Column(Enum(FindingSide), nullable=False)
    entry_id = Column(BigInteger, nullable=False)
    
    # User Request: Foreign Key to BB_staging_bank_entries.portfolio_id
    portfolio_id = Column(String, nullable=True, index=True)
    
    finding_type = Column(Enum(FindingType), nullable=False, index=True)
    finding_reason = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    batch = relationship("BB_recon_batches", back_populates="findings")

# --- 4. Auditability and Change Tracking (Immutable) ---
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class BB_recon_matches_trail(Base):
    __tablename__ = "BB_recon_matches_trail"

    id = Column("ID", Integer, primary_key=True, index=True)
    BB_recon_match_ID = Column(Integer, ForeignKey("BB_recon_matches.ID"), nullable=False)
    batch_id = Column(Integer, ForeignKey("BB_recon_batches.id"), nullable=False)
    
    broker_entry_id = Column(BigInteger, ForeignKey("BB_staging_broker_entries.id"), nullable=False)
    bank_entry_id = Column(BigInteger, ForeignKey("BB_staging_bank_entries.id"), nullable=False)
    
    # User Request: Foreign Key to BB_recon_matches.portfolio_id
    portfolio_id = Column(String, nullable=True)
    
    match_kind = Column(Enum(MatchKind), nullable=False)
    match_id = Column(String, nullable=False)
    canonical_reference = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)
    Action = Column(String, nullable=False)

class BB_recon_findings_trail(Base):
    __tablename__ = "BB_recon_findings_trail"

    id = Column(Integer, primary_key=True, index=True)
    BB_recon_finding_ID = Column(Integer, ForeignKey("BB_recon_findings.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("BB_recon_batches.id"), nullable=False)
    
    side = Column(Enum(FindingSide), nullable=False)
    entry_id = Column(BigInteger, nullable=False)

    # User Request: Foreign Key to BB_recon_findings.portfolio_id
    portfolio_id = Column(String, nullable=True)
    
    finding_type = Column(Enum(FindingType), nullable=False)
    finding_reason = Column(String, nullable=True)
    
    created_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)
    
    # User Request: Modified fields for findings trail
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)
    
    Action = Column(String, nullable=False)

# --- 5. IAM and Security Metadata ---
class Recon_Role_mst(Base):
    __tablename__ = "Recon_Role_mst"

    id = Column("ID", Integer, primary_key=True, index=True)
    Role_Name = Column(String, unique=True, nullable=False)
    Is_Active = Column(Boolean, default=True)
    CreatedBy = Column(String, nullable=True)
    CreatedAt = Column(DateTime, default=datetime.utcnow)

class Recon_Users(Base):
    __tablename__ = "Recon_Users"

    id = Column("Id", Integer, primary_key=True, index=True)
    User_Name = Column(String, nullable=True)
    Email_id = Column(String, unique=True, index=True, nullable=False)
    Is_Active = Column(Boolean, default=True)
    Password = Column(String, nullable=False)
    Role_id = Column(Integer, ForeignKey("Recon_Role_mst.ID"), nullable=False)
    CreatedBy = Column(String, nullable=True)
    CreatedAt = Column(DateTime, default=datetime.utcnow)

    role = relationship("Recon_Role_mst")

class Recon_login_logout(Base):
    __tablename__ = "Recon_login_logout"

    id = Column("ID", Integer, primary_key=True, index=True)
    Name = Column(String, nullable=True)
    Email_id = Column(String, nullable=False)
    login_timestamp = Column(DateTime, default=datetime.utcnow)
    logout_timestamp = Column(DateTime, nullable=True)
    Last_login_timestamp = Column(DateTime, nullable=True)

class Recon_Device_Info(Base):
    __tablename__ = "Recon_Device_Info"

    id = Column("ID", Integer, primary_key=True, index=True)
    Username = Column(String, nullable=False)
    IP = Column(String, nullable=True) 
    Logged_User = Column(String, nullable=True)
    LoggedAt = Column(DateTime, default=datetime.utcnow)
    Lat = Column(Float, nullable=True)
    Lon = Column(Float, nullable=True)


# -------------------------------------------------------------------
# --- CASH vs AR (RECEIVABLES) RECONCILIATION MODELS ---
# -------------------------------------------------------------------

class CR_SourceEnum(str, enum.Enum):
    CASH = "CASH"
    RECEIVABLE = "RECEIVABLE"

class CR_Recon_Files(Base):
    __tablename__ = "CR_Recon_Files"

    id = Column("ID", Integer, primary_key=True, index=True)
    source = Column("Source", Enum(CR_SourceEnum), nullable=False)
    file_name = Column(String, nullable=False)
    file_checksum = Column(String, unique=True, index=True, nullable=False)
    gcs_path = Column(String, nullable=True) # Optional for now
    mime_type = Column(String, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    loaded_by = Column(String, nullable=True)
    loaded_at = Column(DateTime, default=datetime.utcnow)
    
    # New columns for processing status
    processing_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.COMPLETED, nullable=False)
    processing_error = Column(String, nullable=True)
    transaction_count = Column(Integer, nullable=True)

    # Relationships
    cash_batches = relationship("CR_recon_batches", foreign_keys="[CR_recon_batches.cash_file_id]", back_populates="cash_file")
    receivable_batches = relationship("CR_recon_batches", foreign_keys="[CR_recon_batches.receivable_file_id]", back_populates="receivable_file")

class CR_staging_Cash_entries(Base):
    __tablename__ = "CR_staging_Cash_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("CR_Recon_Files.ID"), nullable=False)
    
    value_date = Column(Date, nullable=True, index=True)
    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    vch_id = Column("Vch_ID", String, nullable=True, index=True)
    db_amount = Column("DB_amount", Numeric(18, 2), nullable=True, index=True)
    transaction_name = Column("Transaction_name", String, nullable=True)
    
    validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class CR_staging_Receivable_entries(Base):
    __tablename__ = "CR_staging_Receivable_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("CR_Recon_Files.ID"), nullable=False)
    
    value_date = Column(Date, nullable=True, index=True)
    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    vch_id = Column("Vch_ID", String, nullable=True, index=True)
    cr_amount = Column("CR_amount", Numeric(18, 2), nullable=True, index=True)
    transaction_name = Column("Transaction_name", String, nullable=True)
    
    validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class CR_recon_batches(Base):
    __tablename__ = "CR_recon_batches"

    id = Column(Integer, primary_key=True, index=True)
    cash_file_id = Column(Integer, ForeignKey("CR_Recon_Files.ID"), nullable=False)
    receivable_file_id = Column(Integer, ForeignKey("CR_Recon_Files.ID"), nullable=False)
    
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(Enum(BatchStatus), default=BatchStatus.RUNNING, nullable=False)

    cash_file = relationship("CR_Recon_Files", foreign_keys=[cash_file_id], back_populates="cash_batches")
    receivable_file = relationship("CR_Recon_Files", foreign_keys=[receivable_file_id], back_populates="receivable_batches")
    
    matches = relationship("CR_recon_matches", back_populates="batch")
    findings = relationship("CR_recon_findings", back_populates="batch")

class CR_recon_matches(Base):
    __tablename__ = "CR_recon_matches"

    id = Column("ID", Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("CR_recon_batches.id"), nullable=False)
    
    cash_entry_id = Column(BigInteger, ForeignKey("CR_staging_Cash_entries.id"), nullable=True)
    receivable_entry_id = Column(BigInteger, ForeignKey("CR_staging_Receivable_entries.id"), nullable=True)
    
    portfolio_id = Column("Portfolio_ID", String, nullable=True)
    match_kind = Column(Enum(MatchKind), default=MatchKind.AUTO, nullable=False)
    match_id = Column(String, nullable=False) # e.g. PMSBNK...
    canonical_reference = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    batch = relationship("CR_recon_batches", back_populates="matches")
    cash_entry = relationship("CR_staging_Cash_entries")
    receivable_entry = relationship("CR_staging_Receivable_entries")

class CR_recon_findings(Base):
    __tablename__ = "CR_recon_findings"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("CR_recon_batches.id"), nullable=False)
    
    side = Column(String, nullable=False)
    entry_id = Column(BigInteger, nullable=False) # ID from staging table
    portfolio_id = Column("Porfolio_ID", String, nullable=True)
    
    finding_type = Column(Enum(FindingType), nullable=False)
    finding_reason = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    batch = relationship("CR_recon_batches", back_populates="findings")

class CR_recon_matches_trail(Base):
    __tablename__ = "CR_recon_matches_trail"

    id = Column("ID", Integer, primary_key=True, index=True)
    CR_recon_match_ID = Column(Integer, ForeignKey("CR_recon_matches.ID"), nullable=False)
    batch_id = Column(Integer, ForeignKey("CR_recon_batches.id"), nullable=False)
    
    cash_entry_id = Column(BigInteger, nullable=True)
    receivable_entry_id = Column(BigInteger, nullable=True)
    
    portfolio_id = Column("Portfolio_ID", String, nullable=True)
    match_kind = Column(Enum(MatchKind), nullable=False)
    match_id = Column(String, nullable=False)
    canonical_reference = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)
    Action = Column(String, nullable=False)

class CR_recon_findings_trail(Base):
    __tablename__ = "CR_recon_findings_trail"

    id = Column(Integer, primary_key=True, index=True)
    CR_recon_finding_ID = Column(Integer, ForeignKey("CR_recon_findings.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("CR_recon_batches.id"), nullable=False)
    
    side = Column(String, nullable=False)
    entry_id = Column(BigInteger, nullable=False)
    portfolio_id = Column(String, nullable=True)
    
    finding_type = Column(Enum(FindingType), nullable=False)
    finding_reason = Column(String, nullable=True)
    
    created_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)
    
    Action = Column(String, nullable=False)


# -------------------------------------------------------------------
# --- CASH vs AP (PAYABLES) RECONCILIATION MODELS ---
# -------------------------------------------------------------------

class CAP_SourceEnum(str, enum.Enum):
    CASH = "CASH"
    PAYABLE = "PAYABLE"

class CAP_Recon_Files(Base):
    __tablename__ = "CAP_Recon_Files"

    id = Column("ID", Integer, primary_key=True, index=True)
    source = Column("Source", Enum(CAP_SourceEnum), nullable=False)
    file_name = Column(String, nullable=False)
    file_checksum = Column(String, unique=True, index=True, nullable=False)
    gcs_path = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    loaded_by = Column(String, nullable=True)
    loaded_at = Column(DateTime, default=datetime.utcnow)

    processing_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.COMPLETED, nullable=False)
    processing_error = Column(String, nullable=True)
    transaction_count = Column(Integer, nullable=True)

    cash_batches = relationship("CAP_recon_batches", foreign_keys="[CAP_recon_batches.cash_file_id]", back_populates="cash_file")
    payable_batches = relationship("CAP_recon_batches", foreign_keys="[CAP_recon_batches.payable_file_id]", back_populates="payable_file")

class CAP_staging_Cash_entries(Base):
    """Cash Ledger entries for Cash vs AP recon.
    CSV columns: Portfolio_ID, Val_date, Vch_Id, Transaction_Name, Credit_Amount
    """
    __tablename__ = "CAP_staging_Cash_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("CAP_Recon_Files.ID"), nullable=False)

    value_date = Column(Date, nullable=True, index=True)
    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    vch_id = Column("Vch_Id", String, nullable=True, index=True)
    credit_amount = Column("Credit_Amount", Numeric(18, 2), nullable=True, index=True)
    transaction_name = Column("Transaction_Name", String, nullable=True)

    validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class CAP_staging_Payable_entries(Base):
    """Amount Payable entries for Cash vs AP recon.
    CSV columns: Portfolio_ID, Val_Date, Vch_Id, Transaction_Name, DB_Amount
    """
    __tablename__ = "CAP_staging_Payable_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("CAP_Recon_Files.ID"), nullable=False)

    value_date = Column(Date, nullable=True, index=True)
    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    vch_id = Column("Vch_Id", String, nullable=True, index=True)
    debit_amount = Column("DB_Amount", Numeric(18, 2), nullable=True, index=True)
    transaction_name = Column("Transaction_Name", String, nullable=True)

    validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class CAP_recon_batches(Base):
    __tablename__ = "CAP_recon_batches"

    id = Column(Integer, primary_key=True, index=True)
    cash_file_id = Column(Integer, ForeignKey("CAP_Recon_Files.ID"), nullable=False)
    payable_file_id = Column(Integer, ForeignKey("CAP_Recon_Files.ID"), nullable=False)

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(Enum(BatchStatus), default=BatchStatus.RUNNING, nullable=False)

    cash_file = relationship("CAP_Recon_Files", foreign_keys=[cash_file_id], back_populates="cash_batches")
    payable_file = relationship("CAP_Recon_Files", foreign_keys=[payable_file_id], back_populates="payable_batches")

    matches = relationship("CAP_recon_matches", back_populates="batch")
    findings = relationship("CAP_recon_findings", back_populates="batch")

class CAP_recon_matches(Base):
    __tablename__ = "CAP_recon_matches"

    id = Column("ID", Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("CAP_recon_batches.id"), nullable=False)

    cash_entry_id = Column(BigInteger, ForeignKey("CAP_staging_Cash_entries.id"), nullable=True)
    payable_entry_id = Column(BigInteger, ForeignKey("CAP_staging_Payable_entries.id"), nullable=True)

    portfolio_id = Column("Portfolio_ID", String, nullable=True)
    match_kind = Column(Enum(MatchKind), default=MatchKind.AUTO, nullable=False)
    match_id = Column(String, nullable=False)
    canonical_reference = Column(String, nullable=True)
    reason = Column(String, nullable=True)

    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    batch = relationship("CAP_recon_batches", back_populates="matches")
    cash_entry = relationship("CAP_staging_Cash_entries")
    payable_entry = relationship("CAP_staging_Payable_entries")

class CAP_recon_findings(Base):
    __tablename__ = "CAP_recon_findings"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("CAP_recon_batches.id"), nullable=False)

    side = Column(String, nullable=False)  # CASH or PAYABLE
    entry_id = Column(BigInteger, nullable=False)
    portfolio_id = Column("Portfolio_ID", String, nullable=True)

    finding_type = Column(Enum(FindingType), nullable=False)
    finding_reason = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    batch = relationship("CAP_recon_batches", back_populates="findings")

class CAP_recon_matches_trail(Base):
    __tablename__ = "CAP_recon_matches_trail"

    id = Column("ID", Integer, primary_key=True, index=True)
    CAP_recon_match_ID = Column(Integer, ForeignKey("CAP_recon_matches.ID"), nullable=False)
    batch_id = Column(Integer, ForeignKey("CAP_recon_batches.id"), nullable=False)

    cash_entry_id = Column(BigInteger, nullable=True)
    payable_entry_id = Column(BigInteger, nullable=True)

    portfolio_id = Column("Portfolio_ID", String, nullable=True)
    match_kind = Column(Enum(MatchKind), nullable=False)
    match_id = Column(String, nullable=False)
    canonical_reference = Column(String, nullable=True)
    reason = Column(String, nullable=True)

    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)
    Action = Column(String, nullable=False)

class CAP_recon_findings_trail(Base):
    __tablename__ = "CAP_recon_findings_trail"

    id = Column(Integer, primary_key=True, index=True)
    CAP_recon_finding_ID = Column(Integer, ForeignKey("CAP_recon_findings.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("CAP_recon_batches.id"), nullable=False)

    side = Column(String, nullable=False)
    entry_id = Column(BigInteger, nullable=False)
    portfolio_id = Column(String, nullable=True)

    finding_type = Column(Enum(FindingType), nullable=False)
    finding_reason = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    Action = Column(String, nullable=False)


# -------------------------------------------------------------------
# --- STOCK POSITION RECONCILIATION MODELS ---
# -------------------------------------------------------------------

class SR_SourceEnum(str, enum.Enum):
    STOCK_SUMMARY = "STOCK_SUMMARY"
    TRANSACTION_HISTORY = "TRANSACTION_HISTORY"

class SR_Instrument_Mapping(Base):
    """Symbol <-> Scrip alias mapping table (populated manually or via seed)."""
    __tablename__ = "SR_Instrument_Mapping"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    scrip = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SR_Recon_Files(Base):
    __tablename__ = "SR_Recon_Files"

    id = Column("ID", Integer, primary_key=True, index=True)
    source = Column("Source", Enum(SR_SourceEnum), nullable=False)
    file_name = Column(String, nullable=False)
    file_checksum = Column(String, unique=True, index=True, nullable=False)
    gcs_path = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    loaded_by = Column(String, nullable=True)
    loaded_at = Column(DateTime, default=datetime.utcnow)

    processing_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.COMPLETED, nullable=False)
    processing_error = Column(String, nullable=True)
    transaction_count = Column(Integer, nullable=True)

    summary_batches = relationship("SR_recon_batches", foreign_keys="[SR_recon_batches.summary_file_id]", back_populates="summary_file")
    history_batches = relationship("SR_recon_batches", foreign_keys="[SR_recon_batches.history_file_id]", back_populates="history_file")

class SR_staging_StockSummary_entries(Base):
    """Stock Summary (PMS) parsed rows.
    CSV columns: Portfolio_ID, Symbol, Stock_Name, Qty
    """
    __tablename__ = "SR_staging_StockSummary_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("SR_Recon_Files.ID"), nullable=False)

    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    symbol = Column("Symbol", String, nullable=True, index=True)
    stock_name = Column("Stock_Name", String, nullable=True)
    qty = Column("Qty", Numeric(18, 4), nullable=True)

    validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SR_staging_TransHistory_entries(Base):
    """Transaction History (Meroshare) parsed rows.
    CSV columns: Portfolio_ID, Scrip, Transaction_Date, Balance_After_Transaction
    """
    __tablename__ = "SR_staging_TransHistory_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("SR_Recon_Files.ID"), nullable=False)

    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    scrip = Column("Scrip", String, nullable=True, index=True)
    transaction_date = Column("Transaction_Date", Date, nullable=True, index=True)
    balance_after_transaction = Column("Balance_After_Transaction", Numeric(18, 4), nullable=True)

    validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SR_recon_batches(Base):
    __tablename__ = "SR_recon_batches"

    id = Column(Integer, primary_key=True, index=True)
    summary_file_id = Column(Integer, ForeignKey("SR_Recon_Files.ID"), nullable=False)
    history_file_id = Column(Integer, ForeignKey("SR_Recon_Files.ID"), nullable=False)

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(Enum(BatchStatus), default=BatchStatus.RUNNING, nullable=False)

    summary_file = relationship("SR_Recon_Files", foreign_keys=[summary_file_id], back_populates="summary_batches")
    history_file = relationship("SR_Recon_Files", foreign_keys=[history_file_id], back_populates="history_batches")

    matches = relationship("SR_recon_matches", back_populates="batch")
    findings = relationship("SR_recon_findings", back_populates="batch")

class SR_recon_matches(Base):
    __tablename__ = "SR_recon_matches"

    id = Column("ID", Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("SR_recon_batches.id"), nullable=False)

    summary_entry_id = Column(BigInteger, ForeignKey("SR_staging_StockSummary_entries.id"), nullable=True)
    history_entry_id = Column(BigInteger, ForeignKey("SR_staging_TransHistory_entries.id"), nullable=True)

    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    symbol = Column("Symbol", String, nullable=True, index=True)
    scrip = Column("Scrip", String, nullable=True, index=True)

    match_kind = Column(Enum(MatchKind), default=MatchKind.AUTO, nullable=False)
    match_id = Column(String, nullable=False, index=True)
    reason = Column(String, nullable=True)

    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    batch = relationship("SR_recon_batches", back_populates="matches")
    summary_entry = relationship("SR_staging_StockSummary_entries")
    history_entry = relationship("SR_staging_TransHistory_entries")

class SR_recon_findings(Base):
    __tablename__ = "SR_recon_findings"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("SR_recon_batches.id"), nullable=False)

    side = Column(String, nullable=False)  # STOCK_SUMMARY or TRANSACTION_HISTORY
    entry_id = Column(BigInteger, nullable=False)
    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    symbol_or_scrip = Column("Symbol_Or_Scrip", String, nullable=True, index=True)

    finding_type = Column(Enum(FindingType), nullable=False)
    finding_reason = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    batch = relationship("SR_recon_batches", back_populates="findings")

class SR_recon_matches_trail(Base):
    __tablename__ = "SR_recon_matches_trail"

    id = Column("ID", Integer, primary_key=True, index=True)
    SR_recon_match_ID = Column(Integer, ForeignKey("SR_recon_matches.ID"), nullable=False)
    batch_id = Column(Integer, ForeignKey("SR_recon_batches.id"), nullable=False)

    summary_entry_id = Column(BigInteger, nullable=True)
    history_entry_id = Column(BigInteger, nullable=True)

    portfolio_id = Column("Portfolio_ID", String, nullable=True)
    symbol = Column("Symbol", String, nullable=True)
    scrip = Column("Scrip", String, nullable=True)

    match_kind = Column(Enum(MatchKind), nullable=False)
    match_id = Column(String, nullable=False)
    reason = Column(String, nullable=True)

    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)
    Action = Column(String, nullable=False)

class SR_recon_findings_trail(Base):
    __tablename__ = "SR_recon_findings_trail"

    id = Column(Integer, primary_key=True, index=True)
    SR_recon_finding_ID = Column(Integer, ForeignKey("SR_recon_findings.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("SR_recon_batches.id"), nullable=False)

    side = Column(String, nullable=False)
    entry_id = Column(BigInteger, nullable=False)
    portfolio_id = Column(String, nullable=True)
    symbol_or_scrip = Column("Symbol_Or_Scrip", String, nullable=True)

    finding_type = Column(Enum(FindingType), nullable=False)
    finding_reason = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    Action = Column(String, nullable=False)


# -------------------------------------------------------------------
# --- STOCK MOVEMENT ACQUISITION RECONCILIATION MODELS ---
# -------------------------------------------------------------------

class SMA_SourceEnum(str, enum.Enum):
    STOCK_ACQUISITION = "STOCK_ACQUISITION"
    TRANSACTION_HISTORY = "TRANSACTION_HISTORY"

class SMA_Instrument_Mapping(Base):
    """Symbol <-> Scrip alias mapping for Stock Movement Acquisition."""
    __tablename__ = "SMA_Instrument_Mapping"

    id = Column(Integer, primary_key=True, index=True)
    scrip_a = Column(String, nullable=False, index=True)
    scrip_b = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SMA_Recon_Files(Base):
    __tablename__ = "SMA_Recon_Files"

    id = Column("ID", Integer, primary_key=True, index=True)
    source = Column("Source", Enum(SMA_SourceEnum), nullable=False)
    file_name = Column(String, nullable=False)
    file_checksum = Column(String, unique=True, index=True, nullable=False)
    gcs_path = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    loaded_by = Column(String, nullable=True)
    loaded_at = Column(DateTime, default=datetime.utcnow)

    processing_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING, nullable=False)
    processing_error = Column(String, nullable=True)
    transaction_count = Column(Integer, nullable=True)

    acquisition_batches = relationship("SMA_recon_batches", foreign_keys="[SMA_recon_batches.acquisition_file_id]", back_populates="acquisition_file")
    history_batches = relationship("SMA_recon_batches", foreign_keys="[SMA_recon_batches.history_file_id]", back_populates="history_file")

class SMA_staging_StockAcquisition_entries(Base):
    """Stock Acquisitions parsed rows.
    CSV columns: Portfolio_ID, Scrip, Qty
    """
    __tablename__ = "SMA_staging_StockAcquisition_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("SMA_Recon_Files.ID"), nullable=False)

    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    scrip = Column("Scrip", String, nullable=True, index=True)
    stock_name = Column("Stock_Name", String, nullable=True)
    qty = Column("Qty", Numeric(18, 4), nullable=True)

    validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SMA_staging_TransHistory_entries(Base):
    """Transaction History (Meroshare) for Movement Acquisition.
    CSV columns: Portfolio_ID, Scrip, Transaction_Date, Credit_Quantity
    """
    __tablename__ = "SMA_staging_TransHistory_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("SMA_Recon_Files.ID"), nullable=False)

    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    scrip = Column("Scrip", String, nullable=True, index=True)
    transaction_date = Column("Transaction_Date", Date, nullable=True, index=True)
    credit_quantity = Column("Credit_Quantity", Numeric(18, 4), nullable=True)

    validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SMA_recon_batches(Base):
    __tablename__ = "SMA_recon_batches"

    id = Column(Integer, primary_key=True, index=True)
    acquisition_file_id = Column(Integer, ForeignKey("SMA_Recon_Files.ID"), nullable=False)
    history_file_id = Column(Integer, ForeignKey("SMA_Recon_Files.ID"), nullable=False)

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(Enum(BatchStatus), default=BatchStatus.RUNNING, nullable=False)

    acquisition_file = relationship("SMA_Recon_Files", foreign_keys=[acquisition_file_id], back_populates="acquisition_batches")
    history_file = relationship("SMA_Recon_Files", foreign_keys=[history_file_id], back_populates="history_batches")

    matches = relationship("SMA_recon_matches", back_populates="batch")
    findings = relationship("SMA_recon_findings", back_populates="batch")

class SMA_recon_matches(Base):
    __tablename__ = "SMA_recon_matches"

    id = Column("ID", Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("SMA_recon_batches.id"), nullable=False)

    # Stores representative entry IDs for the group (first entry in the group)
    acquisition_entry_ids = Column("Acquisition_Entry_IDs", String, nullable=True)  # comma-sep IDs
    history_entry_ids = Column("History_Entry_IDs", String, nullable=True)           # comma-sep IDs

    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    scrip = Column("Scrip", String, nullable=True, index=True)
    stock_name = Column("Stock_Name", String, nullable=True)

    acq_qty_sum = Column("Acq_Qty_Sum", Numeric(18, 4), nullable=True)
    th_credit_qty_sum = Column("TH_Credit_Qty_Sum", Numeric(18, 4), nullable=True)

    match_kind = Column(Enum(MatchKind), default=MatchKind.AUTO, nullable=False)
    match_id = Column(String, nullable=False, index=True)
    reason = Column(String, nullable=True)

    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    batch = relationship("SMA_recon_batches", back_populates="matches")

class SMA_recon_findings(Base):
    __tablename__ = "SMA_recon_findings"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("SMA_recon_batches.id"), nullable=False)

    side = Column(String, nullable=False)   # STOCK_ACQUISITION or TRANSACTION_HISTORY
    # For group-level findings, entry_ids is comma-separated; entry_id is first/representative
    entry_id = Column(BigInteger, nullable=True)
    entry_ids = Column("Entry_IDs", String, nullable=True)

    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    scrip = Column("Scrip", String, nullable=True, index=True)
    stock_name = Column("Stock_Name", String, nullable=True)

    acq_qty_sum = Column("Acq_Qty_Sum", Numeric(18, 4), nullable=True)
    th_credit_qty_sum = Column("TH_Credit_Qty_Sum", Numeric(18, 4), nullable=True)

    finding_type = Column(Enum(FindingType), nullable=False)
    finding_reason = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    batch = relationship("SMA_recon_batches", back_populates="findings")

class SMA_recon_matches_trail(Base):
    __tablename__ = "SMA_recon_matches_trail"

    id = Column("ID", Integer, primary_key=True, index=True)
    SMA_recon_match_ID = Column(Integer, ForeignKey("SMA_recon_matches.ID"), nullable=False)
    batch_id = Column(Integer, ForeignKey("SMA_recon_batches.id"), nullable=False)

    acquisition_entry_ids = Column("Acquisition_Entry_IDs", String, nullable=True)
    history_entry_ids = Column("History_Entry_IDs", String, nullable=True)

    portfolio_id = Column("Portfolio_ID", String, nullable=True)
    scrip = Column("Scrip", String, nullable=True)

    acq_qty_sum = Column("Acq_Qty_Sum", Numeric(18, 4), nullable=True)
    th_credit_qty_sum = Column("TH_Credit_Qty_Sum", Numeric(18, 4), nullable=True)

    match_kind = Column(Enum(MatchKind), nullable=False)
    match_id = Column(String, nullable=False)
    reason = Column(String, nullable=True)

    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)
    Action = Column(String, nullable=False)

class SMA_recon_findings_trail(Base):
    __tablename__ = "SMA_recon_findings_trail"

    id = Column(Integer, primary_key=True, index=True)
    SMA_recon_finding_ID = Column(Integer, ForeignKey("SMA_recon_findings.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("SMA_recon_batches.id"), nullable=False)

    side = Column(String, nullable=False)
    entry_id = Column(BigInteger, nullable=True)
    entry_ids = Column("Entry_IDs", String, nullable=True)

    portfolio_id = Column(String, nullable=True)
    scrip = Column(String, nullable=True)

    acq_qty_sum = Column("Acq_Qty_Sum", Numeric(18, 4), nullable=True)
    th_credit_qty_sum = Column("TH_Credit_Qty_Sum", Numeric(18, 4), nullable=True)

    finding_type = Column(Enum(FindingType), nullable=False)
    finding_reason = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    Action = Column(String, nullable=False)


# =============================================================================
# SML — Stock Movement Liquidation Reconciliation
# =============================================================================

class SML_SourceEnum(str, enum.Enum):
    STOCK_LIQUIDATION   = "STOCK_LIQUIDATION"
    TRANSACTION_HISTORY = "TRANSACTION_HISTORY"


class SML_Recon_Files(Base):
    """Uploaded file record for Stock Movement Liquidation reconciliation."""
    __tablename__ = "SML_Recon_Files"

    id = Column("ID", Integer, primary_key=True, index=True)
    source = Column("Source", Enum(SML_SourceEnum), nullable=False)
    file_name = Column(String, nullable=False)
    file_checksum = Column(String, unique=True, index=True, nullable=False)
    gcs_path = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    loaded_by = Column(String, nullable=True)
    loaded_at = Column(DateTime, default=datetime.utcnow)

    processing_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING, nullable=False)
    processing_error = Column(String, nullable=True)
    transaction_count = Column(Integer, nullable=True)

    liquidation_batches = relationship("SML_recon_batches", foreign_keys="[SML_recon_batches.liquidation_file_id]", back_populates="liquidation_file")
    history_batches     = relationship("SML_recon_batches", foreign_keys="[SML_recon_batches.history_file_id]",     back_populates="history_file")


class SML_staging_StockLiquidation_entries(Base):
    """Stock Liquidation parsed rows.
    CSV columns: Portfolio_ID, Scrip, Stock_Name (optional), Qty
    """
    __tablename__ = "SML_staging_StockLiquidation_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("SML_Recon_Files.ID"), nullable=False)

    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    scrip        = Column("Scrip",        String, nullable=True, index=True)
    stock_name   = Column("Stock_Name",   String, nullable=True)
    qty          = Column("Qty",          Numeric(18, 4), nullable=True)

    validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SML_staging_TransHistory_entries(Base):
    """Transaction History (Meroshare) for Movement Liquidation.
    CSV columns: Portfolio_ID, Scrip, Transaction_Date, Debit_Quantity
    """
    __tablename__ = "SML_staging_TransHistory_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("SML_Recon_Files.ID"), nullable=False)

    portfolio_id      = Column("Portfolio_ID",      String,         nullable=True, index=True)
    scrip             = Column("Scrip",             String,         nullable=True, index=True)
    transaction_date  = Column("Transaction_Date",  Date,           nullable=True, index=True)
    debit_quantity    = Column("Debit_Quantity",    Numeric(18, 4), nullable=True)

    validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SML_recon_batches(Base):
    __tablename__ = "SML_recon_batches"

    id                  = Column(Integer, primary_key=True, index=True)
    liquidation_file_id = Column(Integer, ForeignKey("SML_Recon_Files.ID"), nullable=False)
    history_file_id     = Column(Integer, ForeignKey("SML_Recon_Files.ID"), nullable=False)

    started_at   = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status       = Column(Enum(BatchStatus), default=BatchStatus.RUNNING, nullable=False)

    liquidation_file = relationship("SML_Recon_Files", foreign_keys=[liquidation_file_id], back_populates="liquidation_batches")
    history_file     = relationship("SML_Recon_Files", foreign_keys=[history_file_id],     back_populates="history_batches")

    matches  = relationship("SML_recon_matches",  back_populates="batch")
    findings = relationship("SML_recon_findings", back_populates="batch")


class SML_recon_matches(Base):
    __tablename__ = "SML_recon_matches"

    id       = Column("ID", Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("SML_recon_batches.id"), nullable=False)

    liquidation_entry_ids = Column("Liquidation_Entry_IDs", String, nullable=True)  # comma-sep IDs
    history_entry_ids     = Column("History_Entry_IDs",     String, nullable=True)  # comma-sep IDs

    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    scrip        = Column("Scrip",        String, nullable=True, index=True)
    stock_name   = Column("Stock_Name",   String, nullable=True)

    liq_qty_sum      = Column("Liq_Qty_Sum",      Numeric(18, 4), nullable=True)
    th_debit_qty_sum = Column("TH_Debit_Qty_Sum", Numeric(18, 4), nullable=True)

    match_kind = Column(Enum(MatchKind), default=MatchKind.AUTO, nullable=False)
    match_id   = Column(String, nullable=False, index=True)
    reason     = Column(String, nullable=True)

    created_by  = Column(String, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    batch = relationship("SML_recon_batches", back_populates="matches")


class SML_recon_findings(Base):
    __tablename__ = "SML_recon_findings"

    id       = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("SML_recon_batches.id"), nullable=False)

    side      = Column(String, nullable=False)   # STOCK_LIQUIDATION or TRANSACTION_HISTORY
    entry_id  = Column(BigInteger, nullable=True)
    entry_ids = Column("Entry_IDs", String, nullable=True)

    portfolio_id = Column("Portfolio_ID", String, nullable=True, index=True)
    scrip        = Column("Scrip",        String, nullable=True, index=True)
    stock_name   = Column("Stock_Name",   String, nullable=True)

    liq_qty_sum      = Column("Liq_Qty_Sum",      Numeric(18, 4), nullable=True)
    th_debit_qty_sum = Column("TH_Debit_Qty_Sum", Numeric(18, 4), nullable=True)

    finding_type   = Column(Enum(FindingType), nullable=False)
    finding_reason = Column(String, nullable=True)

    created_at  = Column(DateTime, default=datetime.utcnow)
    created_by  = Column(String, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    batch = relationship("SML_recon_batches", back_populates="findings")


class SML_recon_matches_trail(Base):
    __tablename__ = "SML_recon_matches_trail"

    id                  = Column("ID", Integer, primary_key=True, index=True)
    SML_recon_match_ID  = Column(Integer, ForeignKey("SML_recon_matches.ID"), nullable=False)
    batch_id            = Column(Integer, ForeignKey("SML_recon_batches.id"), nullable=False)

    liquidation_entry_ids = Column("Liquidation_Entry_IDs", String, nullable=True)
    history_entry_ids     = Column("History_Entry_IDs",     String, nullable=True)

    portfolio_id = Column("Portfolio_ID", String, nullable=True)
    scrip        = Column("Scrip",        String, nullable=True)

    liq_qty_sum      = Column("Liq_Qty_Sum",      Numeric(18, 4), nullable=True)
    th_debit_qty_sum = Column("TH_Debit_Qty_Sum", Numeric(18, 4), nullable=True)

    match_kind = Column(Enum(MatchKind), nullable=False)
    match_id   = Column(String, nullable=False)
    reason     = Column(String, nullable=True)

    created_by  = Column(String, nullable=True)
    created_at  = Column(DateTime, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)
    Action      = Column(String, nullable=False)


class SML_recon_findings_trail(Base):
    __tablename__ = "SML_recon_findings_trail"

    id                    = Column(Integer, primary_key=True, index=True)
    SML_recon_finding_ID  = Column(Integer, ForeignKey("SML_recon_findings.id"), nullable=False)
    batch_id              = Column(Integer, ForeignKey("SML_recon_batches.id"),   nullable=False)

    side      = Column(String, nullable=False)
    entry_id  = Column(BigInteger, nullable=True)
    entry_ids = Column("Entry_IDs", String, nullable=True)

    portfolio_id = Column(String, nullable=True)
    scrip        = Column(String, nullable=True)

    liq_qty_sum      = Column("Liq_Qty_Sum",      Numeric(18, 4), nullable=True)
    th_debit_qty_sum = Column("TH_Debit_Qty_Sum", Numeric(18, 4), nullable=True)

    finding_type   = Column(Enum(FindingType), nullable=False)
    finding_reason = Column(String, nullable=True)

    created_at  = Column(DateTime, nullable=True)
    created_by  = Column(String, nullable=True)
    Modified_by = Column(String, nullable=True)
    Modified_at = Column(DateTime, nullable=True)

    Action = Column(String, nullable=False)
