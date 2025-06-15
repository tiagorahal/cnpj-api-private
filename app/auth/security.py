import aiosqlite
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from pydantic import BaseModel, EmailStr
import bcrypt
import jwt
import secrets
import datetime

# CONFIGURAÇÕES
SECRET_KEY = "CHAVE-MUITO-FORTE-AQUI"  # troque depois
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
DATABASE_AUTH = "database/security.db"

app = FastAPI(title="API com Autenticação")

# MODELS

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# UTILITÁRIOS

async def get_user_by_email(email: str):
    async with aiosqlite.connect(DATABASE_AUTH) as db:
        db.row_factory = aiosqlite.Row
        result = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await result.fetchone()
        await result.close()
        return dict(row) if row else None

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode())

def create_access_token(data: dict, expires_delta=None):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + (expires_delta or datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ROTAS

@app.post("/register")
async def register(user: UserCreate):
    existing_user = await get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Usuário já cadastrado")

    hashed_pw = hash_password(user.password)
    confirmation_token = secrets.token_urlsafe(32)

    async with aiosqlite.connect(DATABASE_AUTH) as db:
        await db.execute("""
            INSERT INTO users (email, password_hash, confirmation_token)
            VALUES (?, ?, ?)
        """, (user.email, hashed_pw, confirmation_token))
        await db.commit()

    # Simulando envio de email:
    print(f"Simulando envio de email para {user.email}")
    print(f"Link de confirmação: http://localhost:8000/confirm/{confirmation_token}")

    return {"message": "Cadastro realizado. Verifique seu email para confirmação."}

@app.get("/confirm/{token}")
async def confirm_email(token: str):
    async with aiosqlite.connect(DATABASE_AUTH) as db:
        await db.execute("""
            UPDATE users SET email_confirmed = 1, confirmation_token = NULL
            WHERE confirmation_token = ?
        """, (token,))
        await db.commit()

    return {"message": "Email confirmado com sucesso."}

@app.post("/login")
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
