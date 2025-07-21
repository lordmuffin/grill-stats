import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import redis
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import structlog
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET", "grill-stats-jwt-secret-key-2024")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

DATABASE_URL = f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'postgres')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'grill_stats')}"
REDIS_URL = f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/0"

# Logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis setup
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Rate limiting
limiter = Limiter(key_func=get_remote_address, storage_uri=REDIS_URL)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Metrics
auth_requests = Counter('auth_requests_total', 'Total authentication requests', ['method', 'status'])
auth_duration = Histogram('auth_request_duration_seconds', 'Authentication request duration')
token_validations = Counter('token_validations_total', 'Total token validations', ['valid'])

# Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    roles = Column(JSON, default=list)
    permissions = Column(JSON, default=list)
    api_key = Column(String, unique=True, index=True)
    last_login = Column(DateTime)
    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    key_name = Column(String, nullable=False)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    permissions = Column(JSON, default=list)
    rate_limit = Column(Integer, default=1000)
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False)
    ip_address = Column(String)
    user_agent = Column(String)
    success = Column(Boolean, nullable=False)
    failure_reason = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Pydantic models
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    roles: Optional[List[str]] = None
    permissions: Optional[List[str]] = None

class APIKeyCreate(BaseModel):
    key_name: str
    permissions: Optional[List[str]] = []
    rate_limit: Optional[int] = 1000
    expires_in_days: Optional[int] = 365

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    email: Optional[str] = None
    permissions: Optional[List[str]] = []

# Create tables
Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI(
    title="Grill Stats API Gateway Auth Service",
    description="JWT Authentication and Authorization Service",
    version="1.0.0",
    docs_url="/auth/docs",
    redoc_url="/auth/redoc",
    openapi_url="/auth/openapi.json"
)

# Middleware
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "*.grillstats.local"]
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security
security = HTTPBearer()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def create_user(db: Session, user: UserCreate) -> User:
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password,
        full_name=user.full_name,
        roles=["user"],
        permissions=["read:own_data"]
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, email: str, password: str, ip_address: str, user_agent: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    
    # Log login attempt
    attempt = LoginAttempt(
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        success=False
    )
    
    if not user:
        attempt.failure_reason = "User not found"
        db.add(attempt)
        db.commit()
        return None
    
    # Check if account is locked
    if user.account_locked_until and user.account_locked_until > datetime.utcnow():
        attempt.failure_reason = "Account locked"
        db.add(attempt)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is temporarily locked due to too many failed login attempts"
        )
    
    if not verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
            attempt.failure_reason = "Too many failed attempts - account locked"
        else:
            attempt.failure_reason = "Invalid password"
        
        db.add(attempt)
        db.commit()
        return None
    
    # Successful login
    user.failed_login_attempts = 0
    user.account_locked_until = None
    user.last_login = datetime.utcnow()
    attempt.success = True
    
    db.add(attempt)
    db.commit()
    
    return user

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    
    # Check if token is blacklisted
    if redis_client.get(f"blacklist:{token}"):
        token_validations.labels(valid="false").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_token(token)
    if payload is None:
        token_validations.labels(valid="false").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if payload.get("type") != "access":
        token_validations.labels(valid="false").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    email: str = payload.get("sub")
    if email is None:
        token_validations.labels(valid="false").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = get_user_by_email(db, email=email)
    if user is None:
        token_validations.labels(valid="false").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_validations.labels(valid="true").inc()
    return user

# Routes
@app.get("/auth/health")
async def health_check():
    try:
        # Check database
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        
        # Check Redis
        redis_client.ping()
        
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unavailable")

@app.get("/auth/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/auth/register", response_model=Token)
@limiter.limit("5/minute")
async def register(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    with auth_duration.time():
        # Check if user already exists
        if get_user_by_email(db, user.email):
            auth_requests.labels(method="register", status="error").inc()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create user
        db_user = create_user(db, user)
        
        # Create tokens
        access_token = create_access_token(
            data={"sub": db_user.email, "permissions": db_user.permissions}
        )
        refresh_token = create_refresh_token(data={"sub": db_user.email})
        
        # Store refresh token
        redis_client.setex(
            f"refresh:{db_user.id}",
            timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            refresh_token
        )
        
        auth_requests.labels(method="register", status="success").inc()
        logger.info("User registered", user_id=db_user.id, email=db_user.email)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

@app.post("/auth/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, user_login: UserLogin, db: Session = Depends(get_db)):
    with auth_duration.time():
        # Get client info
        ip_address = request.client.host
        user_agent = request.headers.get("user-agent", "")
        
        # Authenticate user
        user = authenticate_user(db, user_login.email, user_login.password, ip_address, user_agent)
        if not user:
            auth_requests.labels(method="login", status="error").inc()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create tokens
        access_token = create_access_token(
            data={"sub": user.email, "permissions": user.permissions}
        )
        refresh_token = create_refresh_token(data={"sub": user.email})
        
        # Store refresh token
        redis_client.setex(
            f"refresh:{user.id}",
            timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            refresh_token
        )
        
        auth_requests.labels(method="login", status="success").inc()
        logger.info("User logged in", user_id=user.id, email=user.email, ip=ip_address)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

@app.post("/auth/refresh", response_model=Token)
@limiter.limit("20/minute")
async def refresh_token(request: Request, refresh_token: str, db: Session = Depends(get_db)):
    with auth_duration.time():
        payload = verify_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            auth_requests.labels(method="refresh", status="error").inc()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        email: str = payload.get("sub")
        user = get_user_by_email(db, email)
        if user is None:
            auth_requests.labels(method="refresh", status="error").inc()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify refresh token in Redis
        stored_token = redis_client.get(f"refresh:{user.id}")
        if stored_token != refresh_token:
            auth_requests.labels(method="refresh", status="error").inc()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create new access token
        access_token = create_access_token(
            data={"sub": user.email, "permissions": user.permissions}
        )
        
        auth_requests.labels(method="refresh", status="success").inc()
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

@app.post("/auth/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # Blacklist the current token
    token = credentials.credentials
    payload = verify_token(token)
    if payload:
        exp = payload.get("exp")
        if exp:
            ttl = exp - int(datetime.utcnow().timestamp())
            if ttl > 0:
                redis_client.setex(f"blacklist:{token}", ttl, "1")
    
    # Remove refresh token
    redis_client.delete(f"refresh:{current_user.id}")
    
    logger.info("User logged out", user_id=current_user.id, email=current_user.email)
    return {"message": "Successfully logged out"}

@app.get("/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "roles": current_user.roles,
        "permissions": current_user.permissions,
        "is_active": current_user.is_active,
        "last_login": current_user.last_login
    }

@app.post("/auth/verify")
async def verify_token_endpoint(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    try:
        user = await get_current_user(credentials, db)
        return {
            "valid": True,
            "user_id": user.id,
            "email": user.email,
            "permissions": user.permissions
        }
    except HTTPException:
        return {"valid": False}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)