from fastapi import APIRouter, HTTPException
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
ACCESS_TOKEN_EXPIRE_MINUTES = 180

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME_SECURITY = os.getenv("DB_NAME_SECURITY")

DATABASE_AUTH = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME_SECURITY}"

engine_auth = create_async_engine(DATABASE_AUTH, future=True)
SessionAUTH = sessionmaker(engine_auth, class_=AsyncSession, expire_on_commit=False)

router = APIRouter()

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

async def get_user_by_email(email: str):
    async with SessionAUTH() as session:
        result = await session.execute(
            text("SELECT * FROM users WHERE email = :email"),
            {"email": email}
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode())

def create_access_token(data: dict, expires_delta=None):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + (expires_delta or datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "jti": secrets.token_hex(16)
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/register")
async def register(user: UserCreate):
    existing_user = await get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Usuário já cadastrado")

    hashed_pw = hash_password(user.password)
    confirmation_token = secrets.token_urlsafe(32)

    async with SessionAUTH() as session:
        await session.execute(
            text("""
                INSERT INTO users (email, password_hash, confirmation_token, is_active)
                VALUES (:email, :password_hash, :confirmation_token, 0)
            """),
            {"email": user.email, "password_hash": hashed_pw, "confirmation_token": confirmation_token}
        )
        await session.commit()

    print(f"Simulando envio de email para {user.email}")
    print(f"Link de confirmação: http://localhost:8000/auth/confirm/{confirmation_token}")

    return {"message": "Cadastro realizado. Verifique seu email para confirmação."}

@router.get("/confirm/{token}")
async def confirm_email(token: str):
    async with SessionAUTH() as session:
        await session.execute(
            text("""
                UPDATE users SET email_confirmed = 1, confirmation_token = NULL
                WHERE confirmation_token = :token
            """),
            {"token": token}
        )
        await session.commit()

    return {"message": "Email confirmado com sucesso (aguardando ativação manual)."}

@router.post("/login")
async def login(user: UserLogin):
    db_user = await get_user_by_email(user.email)
    if not db_user:
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")

    if not verify_password(user.password, db_user['password_hash']):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")

    if not db_user['email_confirmed']:
        raise HTTPException(status_code=403, detail="Email não confirmado")

    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}
