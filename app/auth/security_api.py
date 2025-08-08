"""
app/auth/security_api.py
API de autenticação e segurança adaptada para PostgreSQL
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
import bcrypt
import jwt
import secrets
import datetime
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "180"))

# Configuração do banco único
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cnpj_rede")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

router = APIRouter()

# Modelos Pydantic
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

# Funções auxiliares
async def get_user_by_email(email: str):
    """Busca usuário por email"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT * FROM security.users WHERE email = :email"),
            {"email": email}
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None

def hash_password(password: str) -> str:
    """Hash da senha usando bcrypt"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    """Verifica se a senha corresponde ao hash"""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode())

def create_access_token(data: dict, expires_delta=None):
    """Cria token JWT de acesso"""
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + (
        expires_delta or datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.datetime.utcnow(),
        "jti": secrets.token_hex(16)
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Endpoints
@router.post("/register", response_model=dict)
async def register(user: UserCreate):
    """Registra novo usuário"""
    # Verifica se usuário já existe
    existing_user = await get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    # Hash da senha e token de confirmação
    hashed_pw = hash_password(user.password)
    confirmation_token = secrets.token_urlsafe(32)

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                INSERT INTO security.users 
                (email, password_hash, confirmation_token, is_active, created_at, updated_at)
                VALUES (:email, :password_hash, :confirmation_token, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "email": user.email, 
                "password_hash": hashed_pw, 
                "confirmation_token": confirmation_token
            }
        )
        await session.commit()

    # Em produção, enviar email real
    print(f"[EMAIL SIMULADO] Para: {user.email}")
    print(f"Link de confirmação: http://localhost:8430/auth/confirm/{confirmation_token}")

    return {
        "message": "Cadastro realizado com sucesso. Verifique seu email para confirmação.",
        "email": user.email,
        "confirmation_link": f"/auth/confirm/{confirmation_token}"  # Remover em produção
    }

@router.get("/confirm/{token}")
async def confirm_email(token: str):
    """Confirma email do usuário"""
    async with AsyncSessionLocal() as session:
        # Busca usuário pelo token
        result = await session.execute(
            text("SELECT email FROM security.users WHERE confirmation_token = :token"),
            {"token": token}
        )
        user = result.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="Token inválido ou expirado")
        
        # Confirma email
        await session.execute(
            text("""
                UPDATE security.users 
                SET email_confirmed = 1, 
                    confirmation_token = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE confirmation_token = :token
            """),
            {"token": token}
        )
        await session.commit()

    return {
        "message": "Email confirmado com sucesso! Aguardando ativação pelo administrador.",
        "email": user.email if user else None
    }

@router.post("/login", response_model=TokenResponse)
async def login(user: UserLogin):
    """Login do usuário"""
    # Busca usuário
    db_user = await get_user_by_email(user.email)
    if not db_user:
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")

    # Verifica senha
    if not verify_password(user.password, db_user['password_hash']):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")

    # Verifica confirmação de email
    if not db_user.get('email_confirmed'):
        raise HTTPException(
            status_code=403, 
            detail="Email não confirmado. Verifique sua caixa de entrada."
        )

    # Cria token
    access_token = create_access_token({"sub": user.email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # em segundos
    }

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(current_token: str):
    """Renova o token de acesso"""
    try:
        # Decodifica token atual (mesmo que expirado, para pegar o email)
        payload = jwt.decode(
            current_token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM],
            options={"verify_exp": False}  # Não verifica expiração
        )
        email = payload["sub"]
        
        # Verifica se usuário ainda existe e está ativo
        user = await get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        
        # Cria novo token
        new_token = create_access_token({"sub": email})
        
        return {
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

@router.get("/me")
async def get_current_user_info(
    token: str = Depends(lambda token: token)
):
    """Retorna informações do usuário atual"""
    from .dependencies import get_current_user
    user = await get_current_user(token)
    
    # Busca informações completas
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT email, is_active, email_confirmed,
                       request_count, monthly_request_count,
                       last_request_date, last_request_month,
                       created_at
                FROM security.users 
                WHERE email = :email
            """),
            {"email": user["email"]}
        )
        user_info = result.fetchone()
    
    if not user_info:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    user_dict = dict(user_info._mapping)
    
    # Define plano baseado em is_active
    plano = "Gratuito (50 req/dia)"
    if user_dict["is_active"] == 1:
        plano = "Pago (3000 req/mês)"
    elif user_dict["is_active"] == 2:
        plano = "Ilimitado"
    
    return {
        "email": user_dict["email"],
        "plano": plano,
        "email_confirmado": bool(user_dict["email_confirmed"]),
        "requisicoes_hoje": user_dict["request_count"] or 0,
        "requisicoes_mes": user_dict["monthly_request_count"] or 0,
        "membro_desde": user_dict["created_at"].isoformat() if user_dict["created_at"] else None
    }