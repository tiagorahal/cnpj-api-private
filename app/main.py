from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="CNPJ API PRIVATE",
    version="0.1.0",
    description="API privada para consulta completa de dados CNPJ"
)

@app.get("/api/cnpj/{cnpj}")
async def consultar_cnpj(cnpj: str):
    return JSONResponse({
        "status": "sucesso",
        "registro": cnpj,
        "mensagem": "Este é um exemplo inicial. Integração com banco será feita em breve."
    })
