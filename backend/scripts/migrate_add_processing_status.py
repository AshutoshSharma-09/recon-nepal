"""
Database migration script to add processing status fields to BB_Recon_Files table.
Run this script on your GCP database after deployment.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine
from app.core.config import DATABASE_URL

def run_migration():
    """Add processing status fields to BB_Recon_Files table."""
    
    print(f"Connecting to database: {DATABASE_URL}")
    
    with engine.connect() as conn:
        print("Adding processing_status enum type...")
        
        # Create enum type if it doesn't exist
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE processingstatus AS ENUM (
                    'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'INFECTED'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        conn.commit()
        
        print("Adding columns to BB_Recon_Files table...")
        
        # Add processing_status column
        try:
            conn.execute(text("""
                ALTER TABLE "BB_Recon_Files" 
                ADD COLUMN IF NOT EXISTS processing_status processingstatus 
                NOT NULL DEFAULT 'COMPLETED';
            """))
            conn.commit()
            print("✓ Added processing_status column")
        except Exception as e:
            print(f"Note: processing_status column may already exist: {e}")
            conn.rollback()
        
        # Add processing_error column
        try:
            conn.execute(text("""
                ALTER TABLE "BB_Recon_Files" 
                ADD COLUMN IF NOT EXISTS processing_error VARCHAR;
            """))
            conn.commit()
            print("✓ Added processing_error column")
        except Exception as e:
            print(f"Note: processing_error column may already exist: {e}")
            conn.rollback()
        
        # Add transaction_count column
        try:
            conn.execute(text("""
                ALTER TABLE "BB_Recon_Files" 
                ADD COLUMN IF NOT EXISTS transaction_count INTEGER;
            """))
            conn.commit()
            print("✓ Added transaction_count column")
        except Exception as e:
            print(f"Note: transaction_count column may already exist: {e}")
            conn.rollback()
        
        # Create index on processing_status
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_bb_recon_files_processing_status 
                ON "BB_Recon_Files" (processing_status);
            """))
            conn.commit()
            print("✓ Created index on processing_status")
        except Exception as e:
            print(f"Note: Index may already exist: {e}")
            conn.rollback()
        
        # Update existing records to COMPLETED status
        try:
            result = conn.execute(text("""
                UPDATE "BB_Recon_Files" 
                SET processing_status = 'COMPLETED' 
                WHERE processing_status IS NULL;
            """))
            conn.commit()
            print(f"✓ Updated {result.rowcount} existing records to COMPLETED status")
        except Exception as e:
            print(f"Note: Could not update existing records: {e}")
            conn.rollback()
    
    print("\n✅ Migration completed successfully!")
    print("\nNext steps:")
    print("1. Restart your backend service")
    print("2. Test file upload functionality")
    print("3. Monitor background processing logs")

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
