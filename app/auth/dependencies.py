import os
import jwt
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

# --- Variáveis de ambiente e SQLAlchemy ---
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME_SECURITY = os.getenv("DB_NAME_SECURITY")

DATABASE_AUTH = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME_SECURITY}"

engine_auth = create_async_engine(DATABASE_AUTH, future=True)
SessionAUTH = sessionmaker(engine_auth, class_=AsyncSession, expire_on_commit=False)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    async with SessionAUTH() as session:
        result = await session.execute(
            text("SELECT email, is_active FROM users WHERE email = :email"),
            {"email": email}
        )
        user = result.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        # user is a Row, convert to dict
        return dict(user._mapping)


async def check_and_update_rate_limit(user: dict, qtd_reqs: int = 1):
    email = user["email"]
    is_active = user["is_active"]

    now = datetime.datetime.utcnow()
    today = now.date().isoformat()
    month = now.strftime("%Y-%m")

    async with SessionAUTH() as session:
        result = await session.execute(
            text("""
                SELECT request_count, last_request_date, monthly_request_count, last_request_month
                FROM users WHERE email = :email
            """),
            {"email": email}
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")

        # default values if null
        row = row._mapping  # to dict-like for attribute access
        request_count = row["request_count"] or 0
        last_request_date = row["last_request_date"]
        monthly_request_count = row["monthly_request_count"] or 0
        last_request_month = row["last_request_month"]

        # Rule: is_active 0 = 10/day, 1 = 3000/month, 2 = unlimited
        if is_active == 0:
            if last_request_date != today:
                request_count = 0
            if request_count + qtd_reqs > 10:
                raise HTTPException(429, "Limite diário de requisições atingido para contas não pagas.")
            request_count += qtd_reqs
            await session.execute(
                text("UPDATE users SET request_count = :rc, last_request_date = :ld WHERE email = :email"),
                {"rc": request_count, "ld": today, "email": email}
            )
            await session.commit()
        elif is_active == 1:
            if last_request_month != month:
                monthly_request_count = 0
            if monthly_request_count + qtd_reqs > 3000:
                raise HTTPException(429, "Limite mensal de requisições atingido. Contate o suporte.")
            monthly_request_count += qtd_reqs
            await session.execute(
                text("UPDATE users SET monthly_request_count = :mc, last_request_month = :lm WHERE email = :email"),
                {"mc": monthly_request_count, "lm": month, "email": email}
            )
            await session.commit()
        elif is_active == 2:
            # unlimited, só estatística
            monthly_request_count += qtd_reqs
            await session.execute(
                text("UPDATE users SET monthly_request_count = :mc, last_request_month = :lm WHERE email = :email"),
                {"mc": monthly_request_count, "lm": month, "email": email}
            )
            await session.commit()
        else:
            raise HTTPException(403, "Status de usuário inválido.")
