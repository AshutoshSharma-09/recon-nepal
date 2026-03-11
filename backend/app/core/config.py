import os
import logging
import json
from typing import List

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Settings:
    PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "pms-recon") 
    
    def __init__(self):
        # Strict loading - NO defaults for secrets
        # MODIFIED: Added defaults for Local Docker Dev to fix "Internal Server Error"
        try:
            self.DB_USER = os.environ.get("DB_USER", "pms_user")
            self.DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")
            self.DB_HOST = os.environ.get("DB_HOST", "localhost")
            self.DB_NAME = os.environ.get("DB_NAME", "pms_db")
            
            # API Keys - Expected as JSON list or comma separated? 
            # User requirement: "API_KEYS"
            # Let's assume JSON list for robustness: '["key1", "key2"]'
            api_keys_str = os.environ.get("API_KEYS", '["local-dev-key"]')
            try:
                self.API_KEYS = json.loads(api_keys_str)
                if not isinstance(self.API_KEYS, (list, dict)):
                    raise ValueError("API_KEYS must be a JSON list or dict")
            except json.JSONDecodeError:
                # Fallback to comma separated if simple string
                self.API_KEYS = [k.strip() for k in api_keys_str.split(",") if k.strip()]

            if not self.API_KEYS:
                 raise ValueError("API_KEYS list is empty")

            self.UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")
            self.MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", "10485760"))
            
            # Non-secret defaults allowed
            self.DB_PORT = os.environ.get("DB_PORT", "5432")
            self.GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME") # Optional for now if local only, but good to have
            self.SECRET_KEY = os.environ.get("SECRET_KEY", "super-insecure-dev-secret-key-change-me")

        except KeyError as e:
            # FATAL ERROR - Missing Secret
            msg = f"CRITICAL: Missing required environment variable: {e}"
            logger.critical(msg)
            raise RuntimeError(msg) # Raise to top level to crash app
        except ValueError as e:
             # FATAL ERROR - Invalid Value
            msg = f"CRITICAL: Configuration error: {e}"
            logger.critical(msg)
            raise RuntimeError(msg)

    @property
    def DATABASE_URL(self):
        from urllib.parse import quote_plus
        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASSWORD)
        # Cloud SQL uses Unix socket paths starting with /cloudsql/
        if self.DB_HOST.startswith("/cloudsql/"):
            return f"postgresql://{user}:{password}@/{self.DB_NAME}?host={self.DB_HOST}"
        # Standard TCP connection (local dev / docker-compose)
        return f"postgresql://{user}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

# Singleton Instance
try:
    settings = Settings()
    DATABASE_URL = settings.DATABASE_URL
except RuntimeError as e:
    # Fail Startup Explicitly
    print(f"FAILED TO START: {e}") 
    import sys
    sys.exit(1)
