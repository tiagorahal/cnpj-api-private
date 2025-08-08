"""
app/routers/cnpj_router.py
Router completo para consultas CNPJ - PostgreSQL
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import OAuth2PasswordBearer
import os
import re
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Importa as dependências de autenticação
from ..auth.dependencies import get_current_user, check_and_update_rate_limit

load_dotenv()

router = APIRouter()

# Configuração do banco de dados
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cnpj_rede")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, future=True, pool_size=20, max_overflow=40)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ============ MAPEAMENTOS ============
PORTE_EMPRESA_MAP = {
    "00": "00 - NÃO INFORMADO",
    "01": "01 - MICRO EMPRESA",
    "03": "03 - EMPRESA DE PEQUENO PORTE",
    "05": "05 - DEMAIS"
}

MATRIZ_FILIAL_MAP = {
    "1": "1 - MATRIZ",
    "2": "2 - FILIAL"
}

SITUACAO_CADASTRAL_MAP = {
    "01": "01 - NULA",
    "02": "02 - ATIVA",
    "03": "03 - SUSPENSA",
    "04": "04 - INAPTA",
    "08": "08 - BAIXADA"
}

IDENTIFICADOR_SOCIO_MAP = {
    "1": "1 - PESSOA JURÍDICA",
    "2": "2 - PESSOA FÍSICA",
    "3": "3 - ESTRANGEIRO"
}

FAIXA_ETARIA_MAP = {
    "0": "0 - Não se aplica",
    "1": "1 - 0 a 12 anos",
    "2": "2 - 13 a 20 anos",
    "3": "3 - 21 a 30 anos",
    "4": "4 - 31 a 40 anos",
    "5": "5 - 41 a 50 anos",
    "6": "6 - 51 a 60 anos",
    "7": "7 - Acima de 60 anos",
    "8": "8 - 71 a 80 anos",
    "9": "9 - Acima de 80 anos"
}

QUALIFICACAO_REPRESENTANTE_MAP = {
    "00": "00 - Não informada"
}

# ============ FUNÇÕES AUXILIARES ============

async def require_active_user(user: dict = Depends(get_current_user)):
    """Requer usuário ativo (plano pago ou ilimitado)"""
    if user['is_active'] not in [1, 2]:
        raise HTTPException(403, "Acesso restrito a usuários ativos (planos limitados ou ilimitados).")
    return user

def sanitize_cnpj(cnpj: str) -> str:
    """Remove formatação e valida CNPJ"""
    cnpj_numbers = re.sub(r"\D", "", cnpj).zfill(14)
    if len(cnpj_numbers) != 14:
        raise HTTPException(status_code=422, detail="CNPJ deve ter 14 dígitos")
    return cnpj_numbers

def limpar_cnpj_dict(d):
    """Limpa CNPJs em dicionário"""
    for k in d:
        if (k == "cnpj" or k == "cnpj_basico") and d[k]:
            d[k] = re.sub(r"\D", "", str(d[k]))
    return d

def mascarar_cpf(cpf_cnpj: str) -> str:
    """Mascara CPF/CNPJ para privacidade"""
    if not cpf_cnpj:
        return cpf_cnpj
    if len(cpf_cnpj) == 11:
        return f"***{cpf_cnpj[3:9]}**"
    elif len(cpf_cnpj) == 14:
        return f"***{cpf_cnpj[6:9]}**"
    return cpf_cnpj

def limpar_espacos(texto):
    """Remove espaços extras"""
    if not texto:
        return ""
    return re.sub(r'\s+', ' ', str(texto)).strip()

async def lookup_descricao(session, tabela, codigo):
    """Busca descrição de código em tabela auxiliar"""
    if not codigo:
        return None
    
    result = await session.execute(
        text(f"SELECT descricao FROM cnpj.{tabela} WHERE codigo = :codigo"),
        {"codigo": codigo}
    )
    row = result.first()
    if row:
        return f"{codigo} - {row.descricao}"
    return codigo

async def montar_cnpj_completo(session, cnpj):
    """Monta resposta completa do CNPJ"""
    # Busca estabelecimento
    result = await session.execute(
        text("SELECT * FROM cnpj.estabelecimento WHERE cnpj = :cnpj"),
        {"cnpj": cnpj}
    )
    est_row = result.first()
    if not est_row:
        return None

    est_dict = dict(est_row._mapping)
    cnpj_basico = est_dict["cnpj_basico"]

    # Busca empresa
    result = await session.execute(
        text("SELECT * FROM cnpj.empresas WHERE cnpj_basico = :cnpj_basico"),
        {"cnpj_basico": cnpj_basico}
    )
    emp_row = result.first()
    emp_dict = dict(emp_row._mapping) if emp_row else {}

    # Busca simples
    result = await session.execute(
        text("SELECT * FROM cnpj.simples WHERE cnpj_basico = :cnpj_basico"),
        {"cnpj_basico": cnpj_basico}
    )
    simp_row = result.first()
    simp_dict = dict(simp_row._mapping) if simp_row else {}

    # Formatações básicas
    porte_empresa_formatado = PORTE_EMPRESA_MAP.get(emp_dict.get("porte_empresa"), emp_dict.get("porte_empresa"))
    matriz_filial_formatado = MATRIZ_FILIAL_MAP.get(est_dict.get("matriz_filial"), est_dict.get("matriz_filial"))
    situacao_cadastral_formatado = SITUACAO_CADASTRAL_MAP.get(est_dict.get("situacao_cadastral"), est_dict.get("situacao_cadastral"))
    opcao_simples_formatado = "SIM" if simp_dict.get("opcao_simples") == "S" else "NÃO"
    opcao_mei_formatado = "SIM" if simp_dict.get("opcao_mei") == "S" else "NÃO"
    
    complemento_limpo = limpar_espacos(est_dict.get("complemento"))

    # Lookups de descrições
    municipio_formatado = await lookup_descricao(session, "municipio", est_dict.get("municipio"))
    natureza_juridica_formatado = await lookup_descricao(session, "natureza_juridica", emp_dict.get("natureza_juridica"))
    motivo_situacao_cadastral_formatado = await lookup_descricao(session, "motivo", est_dict.get("motivo_situacao_cadastral"))
    cnae_fiscal_formatado = await lookup_descricao(session, "cnae", est_dict.get("cnae_fiscal"))

    # CNAEs secundários
    cnae_fiscal_secundaria_formatado = []
    if est_dict.get("cnae_fiscal_secundaria"):
        for cnae_sec in est_dict["cnae_fiscal_secundaria"].split(","):
            cnae_sec = cnae_sec.strip()
            if cnae_sec:
                descricao = await lookup_descricao(session, "cnae", cnae_sec)
                if descricao:
                    cnae_fiscal_secundaria_formatado.append(descricao)

    # Monta objeto empresa
    empresa = {
        "cnpj": cnpj,
        "cnpj_basico": est_dict.get("cnpj_basico"),
        "razao_social": emp_dict.get("razao_social"),
        "nome_fantasia": est_dict.get("nome_fantasia"),
        "porte_empresa": porte_empresa_formatado,
        "tipo_logradouro": est_dict.get("tipo_logradouro"),
        "logradouro": est_dict.get("logradouro"),
        "numero": est_dict.get("numero"),
        "complemento": complemento_limpo,
        "bairro": est_dict.get("bairro"),
        "cep": est_dict.get("cep"),
        "uf": est_dict.get("uf"),
        "municipio": municipio_formatado,
        "ddd1": est_dict.get("ddd1"),
        "telefone1": est_dict.get("telefone1"),
        "ddd2": est_dict.get("ddd2"),
        "telefone2": est_dict.get("telefone2"),
        "ddd_fax": est_dict.get("ddd_fax"),
        "fax": est_dict.get("fax"),
        "correio_eletronico": est_dict.get("correio_eletronico"),
        "data_inicio_atividades": est_dict.get("data_inicio_atividades"),
        "cnpj_ordem": est_dict.get("cnpj_ordem"),
        "cnpj_dv": est_dict.get("cnpj_dv"),
        "matriz_filial": matriz_filial_formatado,
        "capital_social": float(emp_dict.get("capital_social", 0)) if emp_dict.get("capital_social") else 0,
        "ente_federativo_responsavel": emp_dict.get("ente_federativo_responsavel"),
        "situacao_cadastral": situacao_cadastral_formatado,
        "pais": est_dict.get("pais"),
        "nome_cidade_exterior": est_dict.get("nome_cidade_exterior"),
        "data_situacao_cadastral": est_dict.get("data_situacao_cadastral"),
        "motivo_situacao_cadastral": motivo_situacao_cadastral_formatado,
        "cnae_fiscal": cnae_fiscal_formatado,
        "cnae_fiscal_secundaria": cnae_fiscal_secundaria_formatado,
        "situacao_especial": est_dict.get("situacao_especial"),
        "data_situacao_especial": est_dict.get("data_situacao_especial"),
        "natureza_juridica": natureza_juridica_formatado,
        "qualificacao_responsavel": await lookup_descricao(session, "qualificacao_socio", emp_dict.get("qualificacao_responsavel")),
        "opcao_simples": opcao_simples_formatado,
        "data_opcao_simples": simp_dict.get("data_opcao_simples"),
        "data_exclusao_simples": simp_dict.get("data_exclusao_simples"),
        "opcao_mei": opcao_mei_formatado,
        "data_opcao_mei": simp_dict.get("data_opcao_mei"),
        "data_exclusao_mei": simp_dict.get("data_exclusao_mei")
    }

    # Busca sócios
    result = await session.execute(
        text("SELECT * FROM cnpj.socios WHERE cnpj = :cnpj"),
        {"cnpj": cnpj}
    )
    socios_rows = result.fetchall()

    socios_list = []
    for row in socios_rows:
        socio_dict = dict(row._mapping)
        socios_list.append({
            "cnpj": socio_dict.get("cnpj"),
            "identificador_de_socio": IDENTIFICADOR_SOCIO_MAP.get(socio_dict.get("identificador_de_socio"), socio_dict.get("identificador_de_socio")),
            "nome_socio": socio_dict.get("nome_socio"),
            "cnpj_cpf_socio": mascarar_cpf(socio_dict.get("cnpj_cpf_socio")),
            "qualificacao_socio": await lookup_descricao(session, "qualificacao_socio", socio_dict.get("qualificacao_socio")),
            "data_entrada_sociedade": socio_dict.get("data_entrada_sociedade"),
            "pais": await lookup_descricao(session, "pais", socio_dict.get("pais")),
            "representante_legal": mascarar_cpf(socio_dict.get("representante_legal")),
            "nome_representante": socio_dict.get("nome_representante"),
            "qualificacao_representante_legal": await lookup_descricao(session, "qualificacao_socio", socio_dict.get("qualificacao_representante_legal")),
            "faixa_etaria": FAIXA_ETARIA_MAP.get(socio_dict.get("faixa_etaria"), socio_dict.get("faixa_etaria"))
        })

    return {"empresa": empresa, "socios": socios_list}

# ============ ENDPOINTS ============

@router.get("/{cnpj}")
async def consultar_cnpj(cnpj: str, user: dict = Depends(get_current_user)):
    """Consulta completa de CNPJ"""
    cnpj = sanitize_cnpj(cnpj)
    
    async with AsyncSessionLocal() as session:
        await check_and_update_rate_limit(user, qtd_reqs=1)
        item = await montar_cnpj_completo(session, cnpj)
        if not item:
            raise HTTPException(status_code=404, detail="CNPJ não encontrado")
        return item

@router.get("/uf/{uf}")
async def listar_por_uf(
    uf: str,
    page: int = Query(1, ge=1),
    user: dict = Depends(require_active_user)
):
    """Lista CNPJs por UF"""
    uf = uf.upper().strip()
    page_size = 50
    offset = (page - 1) * page_size

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT cnpj FROM cnpj.estabelecimento WHERE uf = :uf LIMIT :limit OFFSET :offset"),
            {"uf": uf, "limit": page_size, "offset": offset}
        )
        rows = result.fetchall()
        
        await check_and_update_rate_limit(user, qtd_reqs=len(rows))

        lista = []
        for r in rows:
            cnpj = r.cnpj
            item = await montar_cnpj_completo(session, cnpj)
            if item:
                lista.append(item)
        
        return {
            "uf": uf,
            "page": page,
            "page_size": page_size,
            "total_retornados": len(lista),
            "resultado": lista
        }

@router.get("/municipio/{nome_municipio}")
async def listar_por_municipio(
    nome_municipio: str,
    page: int = Query(1, ge=1),
    user: dict = Depends(require_active_user)
):
    """Lista CNPJs por município"""
    page_size = 50
    offset = (page - 1) * page_size

    async with AsyncSessionLocal() as session:
        # Busca códigos do município
        result = await session.execute(
            text("SELECT codigo FROM cnpj.municipio WHERE UPPER(descricao) LIKE :desc"),
            {"desc": f"%{nome_municipio.upper()}%"}
        )
        municipios = result.fetchall()

        if not municipios:
            return {"municipio": nome_municipio, "resultado": []}

        # Se sua coluna municipio é INT, converta para int, se for VARCHAR, mantenha str
        codigos = [str(row.codigo) for row in municipios]

        # CORREÇÃO AQUI:
        result = await session.execute(
            text("""
                SELECT cnpj FROM cnpj.estabelecimento
                WHERE municipio = ANY(:codigos)
                LIMIT :limit OFFSET :offset
            """),
            {"codigos": codigos, "limit": page_size, "offset": offset}
        )
        rows = result.fetchall()
        cnpjs = [row.cnpj for row in rows]

        await check_and_update_rate_limit(user, qtd_reqs=len(cnpjs))

        lista = []
        for cnpj in cnpjs:
            item = await montar_cnpj_completo(session, cnpj)
            if item:
                lista.append(item)

        return {
            "municipio": nome_municipio,
            "codigos_encontrados": codigos,
            "page": page,
            "page_size": page_size,
            "total_retornados": len(lista),
            "resultado": lista
        }

@router.get("/cnae_principal/{cnae}")
async def listar_por_cnae_principal(
    cnae: str,
    page: int = Query(1, ge=1),
    user: dict = Depends(require_active_user)
):
    """Lista CNPJs por CNAE principal"""
    cnae_num = cnae.split(" ")[0].replace("-", "").strip() if "-" in cnae else cnae.strip()
    page_size = 50
    offset = (page - 1) * page_size

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT cnpj FROM cnpj.estabelecimento WHERE cnae_fiscal = :cnae LIMIT :limit OFFSET :offset"),
            {"cnae": cnae_num, "limit": page_size, "offset": offset}
        )
        rows = result.fetchall()
        
        await check_and_update_rate_limit(user, qtd_reqs=len(rows))

        lista = []
        for r in rows:
            cnpj = r.cnpj
            item = await montar_cnpj_completo(session, cnpj)
            if item:
                lista.append(item)
        
        return {
            "cnae_principal": cnae_num,
            "page": page,
            "page_size": page_size,
            "total_retornados": len(lista),
            "resultado": lista
        }

@router.get("/cnae_secundaria/{cnae}")
async def listar_por_cnae_secundaria(
    cnae: str,
    page: int = Query(1, ge=1),
    user: dict = Depends(require_active_user)
):
    """Lista CNPJs por CNAE secundária"""
    cnae_num = cnae.split(" ")[0].replace("-", "").strip() if "-" in cnae else cnae.strip()
    page_size = 50
    offset = (page - 1) * page_size

    like_pattern1 = f"{cnae_num},%"
    like_pattern2 = f"%,{cnae_num},%"
    like_pattern3 = f"%,{cnae_num}"
    like_pattern4 = cnae_num

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT cnpj FROM cnpj.estabelecimento
                WHERE 
                    cnae_fiscal_secundaria LIKE :pat1 OR
                    cnae_fiscal_secundaria LIKE :pat2 OR
                    cnae_fiscal_secundaria LIKE :pat3 OR
                    cnae_fiscal_secundaria = :pat4
                LIMIT :limit OFFSET :offset
            """),
            {
                "pat1": like_pattern1,
                "pat2": like_pattern2,
                "pat3": like_pattern3,
                "pat4": like_pattern4,
                "limit": page_size,
                "offset": offset
            }
        )
        rows = result.fetchall()
        
        await check_and_update_rate_limit(user, qtd_reqs=len(rows))

        lista = []
        for r in rows:
            cnpj = r.cnpj
            item = await montar_cnpj_completo(session, cnpj)
            if item:
                lista.append(item)
        
        return {
            "cnae_secundaria": cnae_num,
            "page": page,
            "page_size": page_size,
            "total_retornados": len(lista),
            "resultado": lista
        }

# Combinação 1: UF + CNAE PRINCIPAL
@router.get("/uf/{uf}/cnae_principal/{cnae}")
async def listar_uf_cnae_principal(
    uf: str,
    cnae: str,
    page: int = Query(1, ge=1),
    user: dict = Depends(require_active_user)
):
    """Lista CNPJs por UF e CNAE principal"""
    cnae_num = cnae.split(" ")[0].replace("-", "").strip() if "-" in cnae else cnae.strip()
    page_size = 50
    offset = (page - 1) * page_size

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT cnpj FROM cnpj.estabelecimento
                WHERE uf = :uf AND cnae_fiscal = :cnae
                LIMIT :limit OFFSET :offset
            """),
            {
                "uf": uf.upper().strip(),
                "cnae": cnae_num,
                "limit": page_size,
                "offset": offset
            }
        )
        rows = result.fetchall()
        
        await check_and_update_rate_limit(user, qtd_reqs=len(rows))

        lista = []
        for r in rows:
            cnpj = r.cnpj
            item = await montar_cnpj_completo(session, cnpj)
            if item:
                lista.append(item)
        
        return {
            "uf": uf,
            "cnae_principal": cnae_num,
            "page": page,
            "page_size": page_size,
            "total_retornados": len(lista),
            "resultado": lista
        }

# Combinação 2: UF + CNAE SECUNDÁRIA
@router.get("/municipio/{nome_municipio}/cnae_secundaria/{cnae}")
async def listar_municipio_cnae_secundaria(
    nome_municipio: str,
    cnae: str,
    page: int = Query(1, ge=1),
    user: dict = Depends(require_active_user)
):
    """Lista CNPJs por município e CNAE secundária"""
    cnae_num = cnae.split(" ")[0].replace("-", "").strip() if "-" in cnae else cnae.strip()
    page_size = 50
    offset = (page - 1) * page_size
    like_pattern = f"%{cnae_num}%"

    async with AsyncSessionLocal() as session:
        # Buscar códigos do município
        result = await session.execute(
            text("SELECT codigo FROM cnpj.municipio WHERE UPPER(descricao) LIKE :desc"),
            {"desc": f"%{nome_municipio.upper()}%"}
        )
        municipios = result.fetchall()
        
        if not municipios:
            return {"municipio": nome_municipio, "resultado": []}

        codigos = [str(row.codigo) for row in municipios]

        # CORREÇÃO AQUI:
        result = await session.execute(
            text("""
                SELECT cnpj FROM cnpj.estabelecimento
                WHERE municipio = ANY(:codigos)
                  AND cnae_fiscal_secundaria LIKE :like
                LIMIT :limit OFFSET :offset
            """),
            {"codigos": codigos, "like": like_pattern, "limit": page_size, "offset": offset}
        )
        rows = result.fetchall()
        cnpjs = [row.cnpj for row in rows]

        await check_and_update_rate_limit(user, qtd_reqs=len(cnpjs))

        lista = []
        for cnpj in cnpjs:
            item = await montar_cnpj_completo(session, cnpj)
            if item:
                lista.append(item)
        
        return {
            "municipio": nome_municipio,
            "cnae_secundaria": cnae_num,
            "codigos_encontrados": codigos,
            "page": page,
            "page_size": page_size,
            "total_retornados": len(lista),
            "resultado": lista
        }

# Combinação 3: MUNICÍPIO + CNAE PRINCIPAL
router.get("/municipio/{nome_municipio}/cnae_principal/{cnae}")
async def listar_municipio_cnae_principal(
    nome_municipio: str,
    cnae: str,
    page: int = Query(1, ge=1),
    user: dict = Depends(require_active_user)
):
    """Lista CNPJs por município e CNAE principal"""
    cnae_num = cnae.split(" ")[0].replace("-", "").strip() if "-" in cnae else cnae.strip()
    page_size = 50
    offset = (page - 1) * page_size

    async with AsyncSessionLocal() as session:
        # Buscar códigos do município
        result = await session.execute(
            text("SELECT codigo FROM cnpj.municipio WHERE UPPER(descricao) LIKE :desc"),
            {"desc": f"%{nome_municipio.upper()}%"}
        )
        municipios = result.fetchall()
        
        if not municipios:
            return {"municipio": nome_municipio, "resultado": []}

        codigos = [str(row.codigo) for row in municipios]

        # CORREÇÃO AQUI:
        result = await session.execute(
            text("""
                SELECT cnpj FROM cnpj.estabelecimento
                WHERE municipio = ANY(:codigos) AND cnae_fiscal = :cnae
                LIMIT :limit OFFSET :offset
            """),
            {"codigos": codigos, "cnae": cnae_num, "limit": page_size, "offset": offset}
        )
        rows = result.fetchall()
        cnpjs = [row.cnpj for row in rows]

        await check_and_update_rate_limit(user, qtd_reqs=len(cnpjs))

        lista = []
        for cnpj in cnpjs:
            item = await montar_cnpj_completo(session, cnpj)
            if item:
                lista.append(item)
        
        return {
            "municipio": nome_municipio,
            "cnae_principal": cnae_num,
            "codigos_encontrados": codigos,
            "page": page,
            "page_size": page_size,
            "total_retornados": len(lista),
            "resultado": lista
        }

# Combinação 4: MUNICÍPIO + CNAE SECUNDÁRIA  
@router.get("/municipio/{nome_municipio}/cnae_secundaria/{cnae}")
async def listar_municipio_cnae_secundaria(
    nome_municipio: str,
    cnae: str,
    page: int = Query(1, ge=1),
    user: dict = Depends(require_active_user)
):
    """Lista CNPJs por município e CNAE secundária"""
    cnae_num = cnae.split(" ")[0].replace("-", "").strip() if "-" in cnae else cnae.strip()
    page_size = 50
    offset = (page - 1) * page_size
    like_pattern = f"%{cnae_num}%"

    async with AsyncSessionLocal() as session:
        # Buscar códigos do município
        result = await session.execute(
            text("SELECT codigo FROM cnpj.municipio WHERE UPPER(descricao) LIKE :desc"),
            {"desc": f"%{nome_municipio.upper()}%"}
        )
        municipios = result.fetchall()
        
        if not municipios:
            return {"municipio": nome_municipio, "resultado": []}

        codigos = [str(row.codigo) for row in municipios]
        cnpjs = []
        
        for codigo in codigos:
            res = await session.execute(
                text("""
                    SELECT cnpj FROM cnpj.estabelecimento
                    WHERE municipio = :codigo
                      AND cnae_fiscal_secundaria LIKE :like
                    LIMIT :limit OFFSET :offset
                """),
                {"codigo": codigo, "like": like_pattern, "limit": page_size, "offset": offset}
            )
            rows = res.fetchall()
            cnpjs.extend([row.cnpj for row in rows])

        await check_and_update_rate_limit(user, qtd_reqs=len(cnpjs))

        lista = []
        for cnpj in cnpjs:
            item = await montar_cnpj_completo(session, cnpj)
            if item:
                lista.append(item)
        
        return {
            "municipio": nome_municipio,
            "cnae_secundaria": cnae_num,
            "codigos_encontrados": codigos,
            "page": page,
            "page_size": page_size,
            "total_retornados": len(lista),
            "resultado": lista
        }