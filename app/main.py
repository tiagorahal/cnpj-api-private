import aiosqlite
from fastapi import FastAPI, HTTPException, Header
import re

app = FastAPI(
    title="CNPJ API PRIVATE",
    version="0.1.0",
    description="API privada para consulta completa de dados CNPJ"
)

DATABASE_PATH = "database/cnpj.db"
API_KEY = "Rahal4life16chldntm@12"

def sanitize_cnpj(cnpj: str) -> str:
    cnpj_numbers = re.sub(r"\D", "", cnpj)  # Remove tudo que não for número
    cnpj_numbers = cnpj_numbers.zfill(14)   # Preenche zeros à esquerda
    if len(cnpj_numbers) != 14:
        raise HTTPException(status_code=422, detail="CNPJ deve ter 14 dígitos")
    return cnpj_numbers

def limpar_cnpj_dict(d):
    """Remove qualquer formatação dos campos cnpj e cnpj_basico (apenas números)."""
    if isinstance(d, dict):
        for k in d:
            if (k == "cnpj" or k == "cnpj_basico") and d[k] is not None:
                d[k] = re.sub(r"\D", "", str(d[k]))
    return d

@app.get("/api/cnpj/{cnpj}")
async def consultar_cnpj(cnpj: str, x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    cnpj = sanitize_cnpj(cnpj)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Busca dados do estabelecimento
        est = await db.execute("SELECT * FROM estabelecimento WHERE cnpj = ?", (cnpj,))
        est_row = await est.fetchone()
        await est.close()
        if not est_row:
            raise HTTPException(status_code=404, detail="CNPJ não encontrado")

        est_dict = dict(est_row)
        limpar_cnpj_dict(est_dict)
        cnpj_basico = est_dict["cnpj_basico"]

        # Busca dados da empresa (matriz)
        emp = await db.execute("SELECT * FROM empresas WHERE cnpj_basico = ?", (cnpj_basico,))
        emp_row = await emp.fetchone()
        await emp.close()
        emp_dict = dict(emp_row) if emp_row else {}
        limpar_cnpj_dict(emp_dict)

        # Busca dados de simples/mei
        simp = await db.execute("SELECT * FROM simples WHERE cnpj_basico = ?", (cnpj_basico,))
        simp_row = await simp.fetchone()
        await simp.close()
        simp_dict = dict(simp_row) if simp_row else {}
        limpar_cnpj_dict(simp_dict)

        # Busca todos os sócios deste CNPJ
        socios = await db.execute("SELECT * FROM socios WHERE cnpj = ?", (cnpj,))
        socios_rows = await socios.fetchall()
        await socios.close()
        socios_list = []
        for row in socios_rows:
            socio_dict = dict(row)
            limpar_cnpj_dict(socio_dict)
            socios_list.append(socio_dict)

        # Unifica tudo em um JSON
        resultado = {
            "cnpj_pesquisado": cnpj,    # sempre só números!
            "estabelecimento": est_dict,
            "empresa": emp_dict,
            "simples": simp_dict,
            "socios": socios_list
        }

        return resultado
