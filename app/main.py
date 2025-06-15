from fastapi import FastAPI
from app.routers import cnpj_router
from app.auth import security_api

app = FastAPI(
    title="CNPJ API PRIVATE",
    version="3.0.0",
    description="API privada para consulta completa de dados CNPJ com autenticação JWT"
)

app.include_router(security_api.router, prefix="/auth", tags=["Autenticação"])
app.include_router(cnpj_router.router, prefix="/api/cnpj", tags=["CNPJ"])
