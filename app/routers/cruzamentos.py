import aiosqlite
from fastapi import APIRouter, Depends, Query
from app.auth.dependencies import get_current_user


AUX_DB_PATH = "database/cnpj_links_ete.db"

router = APIRouter()

# Permite apenas usuários ativos (is_active 1 ou 2)
async def require_active_user(user: dict = Depends(get_current_user)):
    if user['is_active'] not in [1, 2]:
        raise HTTPException(403, "Acesso restrito a usuários ativos (planos limitados ou ilimitados).")
    return user

def normalize_email(email: str) -> str:
    return email.strip().lower()

def normalize_phone(ddd: str, phone: str) -> str:
    # Junte DDD + telefone, remova tudo que não for dígito
    import re
    full = (ddd or "") + (phone or "")
    return re.sub(r'\D', '', full)

# 1. Buscar todos os CNPJs vinculados a um endereço específico
@router.get("/enderecos/compartilhados")
async def cnpjs_por_endereco(endereco: str, user: dict = Depends(require_active_user)):
    async with aiosqlite.connect(AUX_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id1 FROM link_ete WHERE id2 = ? AND descricao = 'end'",
            (f"EN_{endereco}",)
        )
        cnpjs = [row[0].replace("PJ_", "") for row in await cursor.fetchall()]
        await cursor.close()
    return {"endereco": endereco, "cnpjs": cnpjs}

# 2. Buscar todos os CNPJs vinculados a um telefone específico
@router.get("/emails/compartilhados")
async def emails_compartilhados(email: str, user: dict = Depends(require_active_user)):
    normalized_email = email.strip().lower()
    id2 = f"EM_{normalized_email}"
    cnpjs = []
    async with aiosqlite.connect("database/cnpj_links_ete.db") as db:
        async with db.execute("SELECT id1 FROM link_ete WHERE id2 = ?", (id2,)) as cursor:
            async for row in cursor:
                cnpj = row[0][3:] if row[0].startswith('PJ_') else row[0]
                cnpjs.append(cnpj)
    return {"email": normalized_email, "cnpjs": cnpjs}

@router.get("/telefones/compartilhados")
async def telefones_compartilhados(ddd: str, telefone: str, user: dict = Depends(require_active_user)):
    import re
    normalized_phone = re.sub(r'\D', '', (ddd or "") + (telefone or ""))
    id2 = f"TE_{normalized_phone}"
    cnpjs = []
    async with aiosqlite.connect("database/cnpj_links_ete.db") as db:
        async with db.execute("SELECT id1 FROM link_ete WHERE id2 = ?", (id2,)) as cursor:
            async for row in cursor:
                cnpj = row[0][3:] if row[0].startswith('PJ_') else row[0]
                cnpjs.append(cnpj)
    return {"telefone": normalized_phone, "cnpjs": cnpjs}


# 4. Listar todos os endereços compartilhados por mais de um CNPJ
@router.get("/enderecos/duplicados")
async def enderecos_duplicados(minimo: int = Query(2, ge=2), user: dict = Depends(require_active_user)):
    async with aiosqlite.connect(AUX_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id2, valor FROM link_ete WHERE descricao = 'end' AND valor >= ?",
            (minimo,)
        )
        dados = [{"endereco": row[0][3:], "qtd_cnpjs": row[1]} for row in await cursor.fetchall()]
        await cursor.close()
    return {"enderecos_duplicados": dados}

# 5. Listar todos os telefones duplicados
@router.get("/telefones/duplicados")
async def telefones_duplicados(minimo: int = Query(2, ge=2), user: dict = Depends(require_active_user)):
    async with aiosqlite.connect(AUX_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id2, valor FROM link_ete WHERE descricao = 'tel' AND valor >= ?",
            (minimo,)
        )
        dados = [{"telefone": row[0][3:], "qtd_cnpjs": row[1]} for row in await cursor.fetchall()]
        await cursor.close()
    return {"telefones_duplicados": dados}

# 6. Listar todos os e-mails duplicados
@router.get("/emails/duplicados")
async def emails_duplicados(minimo: int = Query(2, ge=2), user: dict = Depends(require_active_user)):
    async with aiosqlite.connect(AUX_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id2, valor FROM link_ete WHERE descricao = 'email' AND valor >= ?",
            (minimo,)
        )
        dados = [{"email": row[0][3:], "qtd_cnpjs": row[1]} for row in await cursor.fetchall()]
        await cursor.close()
    return {"emails_duplicados": dados}

# 7. Buscar todos os vínculos de um CNPJ
@router.get("/vinculos/{cnpj}")
async def vinculos_do_cnpj(cnpj: str):
    async with aiosqlite.connect(AUX_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id2, descricao, valor FROM link_ete WHERE id1 = ?",
            (f"PJ_{cnpj}",)
        )
        vinculos = []
        for row in await cursor.fetchall():
            tipo = row[1]
            dado = row[0][3:]
            vinculos.append({"tipo": tipo, "dado": dado, "compartilhado_por": row[2]})
        await cursor.close()
    return {"cnpj": cnpj, "vinculos": vinculos}
