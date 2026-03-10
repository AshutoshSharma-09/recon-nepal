from datetime import datetime, timedelta
from typing import Optional
from fastapi import Security, HTTPException, status, Depends
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
from sqlalchemy.orm import Session
from app.database import get_db
from app import models

# Schemas needed for token
from pydantic import BaseModel

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

# Security Schemes
X_API_KEY = APIKeyHeader(name="X-API-Key", auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/access-token", auto_error=False)

# Password hashing
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 day

class Actor:
    def __init__(self, key: str = None, role: str = None, user_id: int = None, name: str = None):
        self.key = key
        self.role = role
        self.user_id = user_id
        self.name = name
        if user_id:
             self.id = f"user:{user_id}"
        else:
             self.id = f"api:{role}"

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    api_key: str = Security(X_API_KEY),
    db: Session = Depends(get_db)
) -> Actor:
    """
    Dual auth mechanism:
    1. Check Bearer Token (User UI) - PRIORITY
    2. Check API Key (Machine/Legacy)
    """
    # 1. JWT Auth (Priority)
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            role: str = payload.get("role")
            if username is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            token_data = TokenData(username=username, role=role)
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        
        user = db.query(models.Recon_Users).filter(models.Recon_Users.Email_id == token_data.username).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        
        # Use User_Name if available, otherwise fallback to Email_id
        display_name = user.User_Name if user.User_Name else user.Email_id
        return Actor(role=user.role.Role_Name, user_id=user.id, name=display_name)

    # 2. API Key Auth (Fallback)
    if api_key:
        keys_config = settings.API_KEYS
        if isinstance(keys_config, dict):
            if api_key in keys_config:
                role = keys_config[api_key]
                return Actor(key=api_key, role=role.lower())
        elif isinstance(keys_config, list):
            if api_key in keys_config:
                return Actor(key=api_key, role="uploader")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )

# Backward compatibility alias if needed
get_api_key = get_current_user
