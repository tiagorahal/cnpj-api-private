import os
import jwt
import aiosqlite
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
import datetime

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
DATABASE_AUTH = "database/security.db"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# dependencies.py

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    async with aiosqlite.connect(DATABASE_AUTH) as db:
        db.row_factory = aiosqlite.Row
        # PEGUE EMAIL E IS_ACTIVE
        result = await db.execute("SELECT email, is_active FROM users WHERE email = ?", (email,))
        user = await result.fetchone()
        await result.close()

        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        # Não precisa validar "if not user['is_active']" aqui, porque status 0 pode ser permitido para request limitado
        # Só retorna o usuário

    return dict(user)


async def check_and_update_rate_limit(user: dict, qtd_reqs: int = 1):
    email = user["email"]
    is_active = user["is_active"]

    now = datetime.datetime.utcnow()
    today = now.date().isoformat()
    month = now.strftime("%Y-%m")

    async with aiosqlite.connect(DATABASE_AUTH) as db:
        db.row_factory = aiosqlite.Row
        res = await db.execute("SELECT request_count, last_request_date, monthly_request_count, last_request_month FROM users WHERE email = ?", (email,))
        row = await res.fetchone()
        await res.close()

        # default values if null
        request_count = row["request_count"] or 0
        last_request_date = row["last_request_date"]
        monthly_request_count = row["monthly_request_count"] or 0
        last_request_month = row["last_request_month"]

        # Rule: is_active 0 = 10/day, 1 = 3000/month, 2 = unlimited
        if is_active == 0:
            if last_request_date != today:
                request_count = 0
            if request_count + qtd_reqs > 10:
                raise HTTPException(429, "Limite diário de requisições atingido para contas não ativas.")
            request_count += qtd_reqs
            await db.execute("UPDATE users SET request_count = ?, last_request_date = ? WHERE email = ?", (request_count, today, email))
            await db.commit()
        elif is_active == 1:
            if last_request_month != month:
                monthly_request_count = 0
            if monthly_request_count + qtd_reqs > 3000:
                raise HTTPException(429, "Limite mensal de requisições atingido. Contate o suporte.")
            monthly_request_count += qtd_reqs
            await db.execute("UPDATE users SET monthly_request_count = ?, last_request_month = ? WHERE email = ?", (monthly_request_count, month, email))
            await db.commit()
        elif is_active == 2:
            # unlimited, só estatística
            monthly_request_count += qtd_reqs
            await db.execute("UPDATE users SET monthly_request_count = ?, last_request_month = ? WHERE email = ?", (monthly_request_count, month, email))
            await db.commit()
        else:
            raise HTTPException(403, "Status de usuário inválido.")
