import aiosqlite
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import OAuth2PasswordBearer
import os
from ..auth.dependencies import get_current_user, check_and_update_rate_limit
import aiosqlite
from fastapi import APIRouter, Depends, Query
import re
import jwt
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
DATABASE_PATH = "database/cnpj.db"
DATABASE_AUTH = "database/security.db"

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

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

def sanitize_cnpj(cnpj: str) -> str:
    cnpj_numbers = re.sub(r"\D", "", cnpj).zfill(14)
    if len(cnpj_numbers) != 14:
        raise HTTPException(status_code=422, detail="CNPJ deve ter 14 dígitos")
    return cnpj_numbers

def limpar_cnpj_dict(d):
    for k in d:
        if (k == "cnpj" or k == "cnpj_basico") and d[k]:
            d[k] = re.sub(r"\D", "", str(d[k]))
    return d

def mascarar_cpf(cpf_cnpj: str) -> str:
    if cpf_cnpj and len(cpf_cnpj) == 11:
        return f"***{cpf_cnpj[3:9]}**"
    elif cpf_cnpj and len(cpf_cnpj) == 14:
        return f"***{cpf_cnpj[6:9]}**"
    return cpf_cnpj

def limpar_espacos(texto):
    if texto is None:
        return None
    return re.sub(r'\s+', ' ', texto).strip()

def limpar_espacos(texto):
    if not texto:
        return ""

async def lookup_descricao(db, tabela, codigo):
    if not codigo:
        return None
    query = f"SELECT descricao FROM {tabela} WHERE codigo = ?"
    cursor = await db.execute(query, (codigo,))
    row = await cursor.fetchone()
    await cursor.close()
    if row:
        return f"{codigo} - {row['descricao']}"
    else:
        return codigo

async def montar_cnpj_completo(db, cnpj):
    # Busca dados do estabelecimento
    est = await db.execute("SELECT * FROM estabelecimento WHERE cnpj = ?", (cnpj,))
    est_row = await est.fetchone()
    await est.close()
    if not est_row:
        return None

    est_dict = dict(est_row)
    limpar_cnpj_dict(est_dict)
    cnpj_basico = est_dict["cnpj_basico"]

    # Busca dados da empresa
    emp = await db.execute("SELECT * FROM empresas WHERE cnpj_basico = ?", (cnpj_basico,))
    emp_row = await emp.fetchone()
    await emp.close()
    emp_dict = dict(emp_row) if emp_row else {}
    limpar_cnpj_dict(emp_dict)

    # Busca dados do simples
    simp = await db.execute("SELECT * FROM simples WHERE cnpj_basico = ?", (cnpj_basico,))
    simp_row = await simp.fetchone()
    await simp.close()
    simp_dict = dict(simp_row) if simp_row else {}
    limpar_cnpj_dict(simp_dict)

    porte_empresa_formatado = PORTE_EMPRESA_MAP.get(emp_dict.get("porte_empresa"), emp_dict.get("porte_empresa"))
    matriz_filial_formatado = MATRIZ_FILIAL_MAP.get(est_dict.get("matriz_filial"), est_dict.get("matriz_filial"))
    situacao_cadastral_formatado = SITUACAO_CADASTRAL_MAP.get(est_dict.get("situacao_cadastral"), est_dict.get("situacao_cadastral"))
    opcao_simples_formatado = "SIM" if simp_dict.get("opcao_simples") == "S" else "NÃO"
    opcao_mei_formatado = "SIM" if simp_dict.get("opcao_mei") == "S" else "NÃO"

    municipio_formatado = await lookup_descricao(db, "municipio", est_dict.get("municipio"))
    natureza_juridica_formatado = await lookup_descricao(db, "natureza_juridica", emp_dict.get("natureza_juridica"))
    motivo_situacao_cadastral_formatado = await lookup_descricao(db, "motivo", est_dict.get("motivo_situacao_cadastral"))
    cnae_fiscal_formatado = await lookup_descricao(db, "cnae", est_dict.get("cnae_fiscal"))
    complemento_limpo = limpar_espacos(est_dict.get("complemento"))

    cnae_fiscal_secundaria_formatado = []
    if est_dict.get("cnae_fiscal_secundaria"):
        for cnae_sec in est_dict["cnae_fiscal_secundaria"].split(","):
            descricao = await lookup_descricao(db, "cnae", cnae_sec.strip())
            cnae_fiscal_secundaria_formatado.append(descricao)

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
        "capital_social": emp_dict.get("capital_social"),
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
        "qualificacao_responsavel": await lookup_descricao(db, "qualificacao_socio", emp_dict.get("qualificacao_responsavel")),
        "opcao_simples": opcao_simples_formatado,
        "data_opcao_simples": simp_dict.get("data_opcao_simples"),
        "data_exclusao_simples": simp_dict.get("data_exclusao_simples"),
        "opcao_mei": opcao_mei_formatado,
        "data_opcao_mei": simp_dict.get("data_opcao_mei"),
        "data_exclusao_mei": simp_dict.get("data_exclusao_mei")
    }

    socios = await db.execute("SELECT * FROM socios WHERE cnpj = ?", (cnpj,))
    socios_rows = await socios.fetchall()
    await socios.close()

    socios_list = []
    for row in socios_rows:
        socio_dict = dict(row)
        limpar_cnpj_dict(socio_dict)
        socios_list.append({
            "cnpj": socio_dict.get("cnpj"),
            "identificador_de_socio": IDENTIFICADOR_SOCIO_MAP.get(socio_dict.get("identificador_de_socio"), socio_dict.get("identificador_de_socio")),
            "nome_socio": socio_dict.get("nome_socio"),
            "cnpj_cpf_socio": mascarar_cpf(socio_dict.get("cnpj_cpf_socio")),
            "qualificacao_socio": await lookup_descricao(db, "qualificacao_socio", socio_dict.get("qualificacao_socio")),
            "data_entrada_sociedade": socio_dict.get("data_entrada_sociedade"),
            "pais": await lookup_descricao(db, "pais", socio_dict.get("pais")),
            "representante_legal": mascarar_cpf(socio_dict.get("representante_legal")),
            "nome_representante": socio_dict.get("nome_representante"),
            "qualificacao_representante_legal": QUALIFICACAO_REPRESENTANTE_MAP.get(socio_dict.get("qualificacao_representante_legal")),
            "faixa_etaria": FAIXA_ETARIA_MAP.get(socio_dict.get("faixa_etaria"), socio_dict.get("faixa_etaria"))
        })

    return {"empresa": empresa, "socios": socios_list}

@router.get("/{cnpj}")
async def consultar_cnpj(cnpj: str, user: dict = Depends(get_current_user)):
    cnpj = sanitize_cnpj(cnpj)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await check_and_update_rate_limit(user, qtd_reqs=1)
        item = await montar_cnpj_completo(db, cnpj)
        if not item:
            raise HTTPException(status_code=404, detail="CNPJ não encontrado")
        return item

@router.get("/uf/{uf}")
async def listar_por_uf(
    uf: str,
    page: int = Query(1, ge=1),
    user: dict = Depends(get_current_user)
):
    uf = uf.upper().strip()
    page_size = 50
    offset = (page - 1) * page_size

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Busca todos os CNPJs para a UF
        cursor = await db.execute(
            "SELECT cnpj FROM estabelecimento WHERE uf = ? LIMIT ? OFFSET ?",
            (uf, page_size, offset)
        )
        results = await cursor.fetchall()
        await cursor.close()
        await check_and_update_rate_limit(user, qtd_reqs=len(results))  # [ADICIONADA]

        lista = []
        for r in results:
            cnpj = r["cnpj"]
            item = await montar_cnpj_completo(db, cnpj)
            if item:
                lista.append(item)
        return {
            "uf": uf,
            "page": page,
            "page_size": page_size,
            "total_retornados": len(lista),
            "resultado": lista
        }

from fastapi import Query

@router.get("/municipio/{nome_municipio}")
async def listar_por_municipio(
    nome_municipio: str,
    page: int = Query(1, ge=1),
    user: dict = Depends(get_current_user)
):
    page_size = 50
    offset = (page - 1) * page_size

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Descobre o(s) código(s) do município pelo nome (case-insensitive)
        cursor = await db.execute(
            "SELECT codigo FROM municipio WHERE descricao LIKE ?",
            (f"%{nome_municipio.upper()}%",)
        )
        municipios = await cursor.fetchall()
        await cursor.close()

        if not municipios:
            return {"municipio": nome_municipio, "resultado": []}

        codigos = [str(row["codigo"]) for row in municipios]

        # Busca os CNPJs para esses códigos de município
        cnpjs = []
        for codigo in codigos:
            cur_cnpj = await db.execute(
                "SELECT cnpj FROM estabelecimento WHERE municipio = ? LIMIT ? OFFSET ?",
                (codigo, page_size, offset)
            )
            results = await cur_cnpj.fetchall()
            await cur_cnpj.close()
            cnpjs.extend([row["cnpj"] for row in results])

        await check_and_update_rate_limit(user, qtd_reqs=len(cnpjs))  # [ADICIONADA]

        lista = []
        for cnpj in cnpjs:
            item = await montar_cnpj_completo(db, cnpj)
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
    user: dict = Depends(get_current_user)
):
    cnae_num = cnae.split(" ")[0].replace("-", "").strip() if "-" in cnae else cnae.strip()
    page_size = 50
    offset = (page - 1) * page_size

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT cnpj FROM estabelecimento WHERE cnae_fiscal = ? LIMIT ? OFFSET ?",
            (cnae_num, page_size, offset)
        )
        results = await cursor.fetchall()
        await cursor.close()

        await check_and_update_rate_limit(user, qtd_reqs=len(results))  # [ADICIONADA]

        lista = []
        for r in results:
            cnpj = r["cnpj"]
            item = await montar_cnpj_completo(db, cnpj)
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
    user: dict = Depends(get_current_user)
):
    cnae_num = cnae.split(" ")[0].replace("-", "").strip() if "-" in cnae else cnae.strip()
    page_size = 50
    offset = (page - 1) * page_size

    # Monta padrão LIKE: pega exatos os 7 números, separados por vírgula ou isolados no campo
    # Ex: ,6201500, ou 6201500, ou ,6201500 ou 6201500 (início/fim/entre)
    like_pattern1 = f"{cnae_num},%"
    like_pattern2 = f"%,{cnae_num},%"
    like_pattern3 = f"%,{cnae_num}"
    like_pattern4 = f"{cnae_num}"  # Campo exatamente igual

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT cnpj FROM estabelecimento
            WHERE 
                cnae_fiscal_secundaria LIKE ? OR
                cnae_fiscal_secundaria LIKE ? OR
                cnae_fiscal_secundaria LIKE ? OR
                cnae_fiscal_secundaria = ?
            LIMIT ? OFFSET ?
            """,
            (like_pattern1, like_pattern2, like_pattern3, like_pattern4, page_size, offset)
        )
        results = await cursor.fetchall()
        await cursor.close()

        await check_and_update_rate_limit(user, qtd_reqs=len(results))

        lista = []
        for r in results:
            cnpj = r["cnpj"]
            item = await montar_cnpj_completo(db, cnpj)
            if item:
                lista.append(item)
        return {
            "cnae_secundaria": cnae_num,
            "page": page,
            "page_size": page_size,
            "total_retornados": len(lista),
            "resultado": lista
        }
