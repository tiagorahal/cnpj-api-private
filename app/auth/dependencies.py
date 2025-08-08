"""
app/auth/dependencies.py
Dependências de autenticação adaptadas para PostgreSQL
"""

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

# Configurações JWT
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

# Configuração do banco único
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cnpj_rede")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Valida o token JWT e retorna o usuário atual"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT email, is_active FROM security.users WHERE email = :email"),
            {"email": email}
        )
        user = result.fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        
        return dict(user._mapping)

async def check_and_update_rate_limit(user: dict, qtd_reqs: int = 1):
    """Verifica e atualiza o limite de requisições do usuário"""
    email = user["email"]
    is_active = user["is_active"]

    now = datetime.datetime.utcnow()
    today = now.date()
    month = now.strftime("%Y-%m")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT request_count, last_request_date, 
                       monthly_request_count, last_request_month
                FROM security.users 
                WHERE email = :email
            """),
            {"email": email}
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")

        # Converter para dict para acesso mais fácil
        row = row._mapping
        request_count = row["request_count"] or 0
        last_request_date = row["last_request_date"]
        monthly_request_count = row["monthly_request_count"] or 0
        last_request_month = row["last_request_month"]

        # Aplicar regras de rate limiting baseadas no plano
        if is_active == 0:  # Plano gratuito: 10 requisições por dia
            # Reset contador diário se mudou o dia
            if str(last_request_date) != today:
                request_count = 0
            
            if request_count + qtd_reqs > 10:
                raise HTTPException(
                    status_code=429, 
                    detail="Limite diário de requisições atingido (10/dia). Faça upgrade para aumentar o limite."
                )
            
            request_count += qtd_reqs
            
            await session.execute(
                text("""
                    UPDATE security.users 
                    SET request_count = :rc, 
                        last_request_date = :ld,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE email = :email
                """),
                {"rc": request_count, "ld": today, "email": email}
            )
            await session.commit()
            
        elif is_active == 1:  # Plano pago: 3000 requisições por mês
            # Reset contador mensal se mudou o mês
            if last_request_month != month:
                monthly_request_count = 0
            
            if monthly_request_count + qtd_reqs > 3000:
                raise HTTPException(
                    status_code=429, 
                    detail="Limite mensal de requisições atingido (3000/mês). Contate o suporte para plano ilimitado."
                )
            
            monthly_request_count += qtd_reqs
            
            await session.execute(
                text("""
                    UPDATE security.users 
                    SET monthly_request_count = :mc, 
                        last_request_month = :lm,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE email = :email
                """),
                {"mc": monthly_request_count, "lm": month, "email": email}
            )
            await session.commit()
            
        elif is_active == 2:  # Plano ilimitado
            # Apenas registra para estatísticas
            if last_request_month != month:
                monthly_request_count = 0
            
            monthly_request_count += qtd_reqs
            
            await session.execute(
                text("""
                    UPDATE security.users 
                    SET monthly_request_count = :mc, 
                        last_request_month = :lm,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE email = :email
                """),
                {"mc": monthly_request_count, "lm": month, "email": email}
            )
            await session.commit()
            
        else:
            raise HTTPException(
                status_code=403, 
                detail="Status de usuário inválido. Contate o suporte."
            )

async def require_admin(user: dict = Depends(get_current_user)):
    """Requer que o usuário seja administrador (is_active = 2)"""
    if user['is_active'] != 2:
        raise HTTPException(
            status_code=403, 
            detail="Acesso restrito a administradores"
        )
    return user