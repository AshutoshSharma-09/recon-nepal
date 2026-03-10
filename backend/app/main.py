import logging
import traceback
import uuid
import sys
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api import endpoints, recon, auth, car_recon, cap_recon, sr_recon, sma_recon, sml_recon
from app.database import engine, get_db, SessionLocal
from app import models
# from app.models import User, UserRole # Removed old models
from app.core import security
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.middleware import CorrelationIdMiddleware

# Logging Setup: Structured JSON
# To implement true JSON logging, we typically use a formatter. 
# For MVP, we'll configure basicConfig but wrap logs manually or use a simple formatter if libraries aren't allowed.
# User Hard Rules: "DO NOT add ... Cloud services". 
# "Use structured (JSON) logging". 
# I'll implement a custom formatter.

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno
        }
        if hasattr(record, "correlation_id"):
             log_obj["correlation_id"] = record.correlation_id
        if hasattr(record, "actor_id"):
             log_obj["actor_id"] = record.actor_id
        
        # Add stack trace if exception
        if record.exc_info:
            log_obj["stack_trace"] = self.formatException(record.exc_info)

        import json
        return json.dumps(log_obj)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("pms_recon")

# Re-enabled for fresh deployment since we are wiping the DB
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="NIMB PMS Reconciliation Tool", version="2.0.0")

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    
    # Log full traceback internally with structured data
    extra = {"correlation_id": correlation_id}
    # Since standard logging adapter isn't set up, we just log straight
    logger.error(f"Internal Server Error: {str(exc)}", exc_info=exc, extra=extra)
    
    # Generic Client Response
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please reference the request ID.",
            "request_id": correlation_id
        }
    )

app.add_middleware(CorrelationIdMiddleware)

# Configure CORS - Allow all origins since Nginx reverse proxy is the gatekeeper
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "NIMB PMS Recon API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


# Include API routers
app.include_router(endpoints.router, prefix="/api/v1")
app.include_router(recon.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(car_recon.router, prefix="/api/v1")
app.include_router(cap_recon.router, prefix="/api/v1")
app.include_router(sr_recon.router, prefix="/api/v1")
app.include_router(sma_recon.router, prefix="/api/v1")
app.include_router(sml_recon.router, prefix="/api/v1")

@app.on_event("startup")
def seed_users():
    db = SessionLocal()
    try:
        # 1. Seed Roles
        roles = ["Admin", "Analyst"]
        role_map = {}
        
        for r_name in roles:
            role_obj = db.query(models.Recon_Role_mst).filter(models.Recon_Role_mst.Role_Name == r_name).first()
            if not role_obj:
                role_obj = models.Recon_Role_mst(Role_Name=r_name, CreatedBy="SYSTEM")
                db.add(role_obj)
                db.flush() # get ID
                print(f"Seeded Role: {r_name}")
            role_map[r_name] = role_obj

        # 2. Seed Admin User
        admin_email = "admin01@nimb"
        admin = db.query(models.Recon_Users).filter(models.Recon_Users.Email_id == admin_email).first()
        if not admin:
            admin_user = models.Recon_Users(
                Email_id=admin_email,
                Password=security.get_password_hash("admin@0001"),
                Role_id=role_map["Admin"].id,
                User_Name="System Admin",
                Is_Active=True,
                CreatedBy="SYSTEM"
            )
            db.add(admin_user)
            print("Seeded Admin User")

        # 3. Seed Analyst
        analyst_email = "ashu009@nimb"
        analyst = db.query(models.Recon_Users).filter(models.Recon_Users.Email_id == analyst_email).first()
        if not analyst:
            analyst_user = models.Recon_Users(
                Email_id=analyst_email,
                Password=security.get_password_hash("ashu@2004"),
                Role_id=role_map["Analyst"].id,
                User_Name="Ashutosh Sharma",
                Is_Active=True,
                CreatedBy="SYSTEM"
            )
            db.add(analyst_user)
            print("Seeded Analyst User")

        db.commit()
    except Exception as e:
        print(f"Error seeding users: {e}")
        db.rollback()
    finally:
        db.close()
