from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from starlette.middleware.base import BaseHTTPMiddleware
import jwt
import os

from app.routers import cnpj_router
from app.auth import security_api

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

app = FastAPI(
    title="CNPJ API PRIVATE",
    version="3.0.0",
    description="API privada para consulta completa de dados CNPJ com autenticação JWT"
)

app.include_router(security_api.router, prefix="/auth", tags=["Autenticação"])
app.include_router(cnpj_router.router, prefix="/api/cnpj", tags=["CNPJ"])


# ---- Middleware para proteger a doc ----
class DocsAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Protege só o /docs e /redoc
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            auth = request.headers.get("Authorization")
            if not auth or not auth.startswith("Bearer "):
                # Pode redirecionar para login ou só negar
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autorizado")
            token = auth.replace("Bearer ", "")
            try:
                jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            except Exception:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido ou expirado")
        return await call_next(request)

app.add_middleware(DocsAuthMiddleware)
# ---- fim do middleware ----
