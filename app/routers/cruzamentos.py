from fastapi import APIRouter, Depends, Query, HTTPException
from app.auth.dependencies import get_current_user
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME_LINKS = os.getenv("DB_NAME_LINKS")  # exemplo: "cnpj_links_ete"

AUX_DB_PATH = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME_LINKS}"
engine_aux = create_async_engine(AUX_DB_PATH, future=True)
SessionAUX = sessionmaker(engine_aux, class_=AsyncSession, expire_on_commit=False)

router = APIRouter()

async def require_active_user(user: dict = Depends(get_current_user)):
    if user['is_active'] not in [1, 2]:
        raise HTTPException(403, "Acesso restrito a usuários ativos (planos limitados ou ilimitados).")
    return user

def normalize_email(email: str) -> str:
    return email.strip().lower()

def normalize_phone(ddd: str, phone: str) -> str:
    import re
    full = (ddd or "") + (phone or "")
    return re.sub(r'\D', '', full)

@router.get("/enderecos/compartilhados")
async def cnpjs_por_endereco(endereco: str, user: dict = Depends(require_active_user)):
    async with SessionAUX() as session:
        result = await session.execute(
            text("SELECT id1 FROM link_ete WHERE id2 = :id2 AND descricao = 'end'"),
            {"id2": f"EN_{endereco}"}
        )
        rows = result.fetchall()
        cnpjs = [row[0].replace("PJ_", "") for row in rows]
    return {"endereco": endereco, "cnpjs": cnpjs}

@router.get("/emails/compartilhados")
async def emails_compartilhados(email: str, user: dict = Depends(require_active_user)):
    normalized_email = email.strip().lower()
    id2 = f"EM_{normalized_email}"
    cnpjs = []
    async with SessionAUX() as session:
        result = await session.execute(
            text("SELECT id1 FROM link_ete WHERE id2 = :id2"),
            {"id2": id2}
        )
        rows = result.fetchall()
        for row in rows:
            cnpj = row[0][3:] if row[0].startswith('PJ_') else row[0]
            cnpjs.append(cnpj)
    return {"email": normalized_email, "cnpjs": cnpjs}

@router.get("/telefones/compartilhados")
async def telefones_compartilhados(ddd: str, telefone: str, user: dict = Depends(require_active_user)):
    import re
    normalized_phone = re.sub(r'\D', '', (ddd or "") + (telefone or ""))
    id2 = f"TE_{normalized_phone}"
    cnpjs = []
    async with SessionAUX() as session:
        result = await session.execute(
            text("SELECT id1 FROM link_ete WHERE id2 = :id2"),
            {"id2": id2}
        )
        rows = result.fetchall()
        for row in rows:
            cnpj = row[0][3:] if row[0].startswith('PJ_') else row[0]
            cnpjs.append(cnpj)
    return {"telefone": normalized_phone, "cnpjs": cnpjs}

@router.get("/enderecos/duplicados")
async def enderecos_duplicados(minimo: int = Query(2, ge=2), user: dict = Depends(require_active_user)):
    async with SessionAUX() as session:
        result = await session.execute(
            text("SELECT id2, valor FROM link_ete WHERE descricao = 'end' AND valor >= :minimo"),
            {"minimo": minimo}
        )
        rows = result.fetchall()
        dados = [{"endereco": row[0][3:], "qtd_cnpjs": row[1]} for row in rows]
    return {"enderecos_duplicados": dados}

@router.get("/telefones/duplicados")
async def telefones_duplicados(minimo: int = Query(2, ge=2), user: dict = Depends(require_active_user)):
    async with SessionAUX() as session:
        result = await session.execute(
            text("SELECT id2, valor FROM link_ete WHERE descricao = 'tel' AND valor >= :minimo"),
            {"minimo": minimo}
        )
        rows = result.fetchall()
        dados = [{"telefone": row[0][3:], "qtd_cnpjs": row[1]} for row in rows]
    return {"telefones_duplicados": dados}

@router.get("/emails/duplicados")
async def emails_duplicados(minimo: int = Query(2, ge=2), user: dict = Depends(require_active_user)):
    async with SessionAUX() as session:
        result = await session.execute(
            text("SELECT id2, valor FROM link_ete WHERE descricao = 'email' AND valor >= :minimo"),
            {"minimo": minimo}
        )
        rows = result.fetchall()
        dados = [{"email": row[0][3:], "qtd_cnpjs": row[1]} for row in rows]
    return {"emails_duplicados": dados}

@router.get("/vinculos/{cnpj}")
async def vinculos_do_cnpj(cnpj: str):
    async with SessionAUX() as session:
        result = await session.execute(
            text("SELECT id2, descricao, valor FROM link_ete WHERE id1 = :id1"),
            {"id1": f"PJ_{cnpj}"}
        )
        rows = result.fetchall()
        vinculos = []
        for row in rows:
            tipo = row[1]
            dado = row[0][3:]
            vinculos.append({"tipo": tipo, "dado": dado, "compartilhado_por": row[2]})
    return {"cnpj": cnpj, "vinculos": vinculos}
