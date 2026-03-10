from datetime import timedelta, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.core import security
from app.models import Recon_Users, Recon_login_logout, Recon_Device_Info
from pydantic import BaseModel

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str
    lat: Optional[float] = None
    lon: Optional[float] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

@router.post("/auth/login", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: LoginRequest,
    db: Session = Depends(get_db)
):
    user = db.query(Recon_Users).filter(Recon_Users.Email_id == form_data.email).first()
    # Note: user.Password is hashed
    if not user or not security.verify_password(form_data.password, user.Password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.Is_Active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Log Login Activity
    try:
        # Get Last Login Timestamp
        last_login_record = db.query(Recon_login_logout).filter(
            Recon_login_logout.Email_id == user.Email_id
        ).order_by(desc(Recon_login_logout.login_timestamp)).first()
        
        last_login_timestamp = None
        if last_login_record:
            last_login_timestamp = last_login_record.login_timestamp

        login_record = Recon_login_logout(
            Name=user.User_Name,
            Email_id=user.Email_id,
            login_timestamp=datetime.utcnow(),
            Last_login_timestamp=last_login_timestamp
        )
        db.add(login_record)
        
        # Log Device Info
        client_ip = request.client.host if request.client else None
        
        device_info = Recon_Device_Info(
            Username=user.Email_id,
            IP=client_ip,
            Logged_User=user.role.Role_Name,
            LoggedAt=datetime.utcnow(),
            Lat=form_data.lat,
            Lon=form_data.lon
        )
        db.add(device_info)
        db.commit()
    except Exception as e:
        # Don't fail login if logging fails, but maybe log error to console
        print(f"Error logging login activity: {e}")
        db.rollback()

    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    # role is a relationship, Role_Name is the field
    access_token = security.create_access_token(
        data={"sub": user.Email_id, "role": user.role.Role_Name}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user.role.Role_Name}

@router.post("/auth/logout")
async def logout(
    current_user: security.Actor = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    # Find the latest login record for this user where logout_timestamp is NULL
    # We use user_id from Actor which corresponds to Recon_Users.id? 
    # Wait, Actor has user_id but Recon_login_logout uses Email_id.
    # Security.get_current_user returns Actor(role=..., user_id=...)
    # We need to get the Email_id.
    # Let's fetch the user again or rely on the fact that we can get email from user_id if needed,
    # OR change get_current_user to return more info. 
    # Actually, get_current_user decodes the token which has "sub" (email).
    # But Actor class in security.py doesn't seem to store "sub"/email directly, only user_id.
    
    # Let's check security.py again. 
    # Actor(role=user.role.Role_Name, user_id=user.id)
    # So we have user_id. We can query Recon_Users to get Email_id.
    
    user = db.query(Recon_Users).filter(Recon_Users.id == current_user.user_id).first()
    if not user:
         raise HTTPException(status_code=404, detail="User not found")
         
    login_record = db.query(Recon_login_logout).filter(
        Recon_login_logout.Email_id == user.Email_id,
        Recon_login_logout.logout_timestamp == None
    ).order_by(desc(Recon_login_logout.login_timestamp)).first()

    if login_record:
        login_record.logout_timestamp = datetime.utcnow()
        db.commit()
        return {"message": "Successfully logged out"}
    
    return {"message": "No active session found"}
