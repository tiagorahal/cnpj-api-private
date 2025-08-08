"""
app/main.py
Aplicação principal FastAPI com PostgreSQL
"""

from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import jwt
import os
from dotenv import load_dotenv
import logging
import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

# Importa routers
from app.routers import cnpj_router, cruzamentos
from app.auth import security_api
from app.auth.dependencies import get_current_user

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Criar aplicação FastAPI
app = FastAPI(
    title="CNPJ API - PostgreSQL",
    version="4.0.0",
    description="""
    API completa para consulta de dados CNPJ com:
    - Base de dados completa da Receita Federal
    - Cruzamento de dados (endereços, telefones, emails compartilhados)
    - Rede de relacionamentos societários
    - Autenticação JWT com rate limiting
    - Banco de dados PostgreSQL otimizado
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique os domínios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTML para página de login da documentação
LOGIN_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Login - CNPJ API</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .login-container {
            background: white;
            padding: 2.5rem;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 400px;
        }
        h2 {
            text-align: center;
            color: #333;
            margin-bottom: 2rem;
            font-size: 1.8rem;
        }
        input {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: transform 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
        }
        button:active {
            transform: translateY(0);
        }
        .error {
            color: #e74c3c;
            text-align: center;
            margin: 10px 0;
            font-size: 14px;
        }
        .success {
            color: #27ae60;
            text-align: center;
            margin: 10px 0;
            font-size: 14px;
        }
        .links {
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 14px;
        }
        .links a {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }
        .links a:hover {
            text-decoration: underline;
        }
        .spinner {
            display: none;
            width: 20px;
            height: 20px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>🔐 CNPJ API</h2>
        <div id="error" class="error"></div>
        <div id="success" class="success"></div>
        <div id="spinner" class="spinner"></div>
        
        <input type="email" id="email" placeholder="Email" autocomplete="email" />
        <input type="password" id="password" placeholder="Senha" autocomplete="current-password" />
        <button onclick="login()" id="loginBtn">Entrar</button>
        
        <div class="links">
            <p>Não tem conta? <a href="/auth/register">Cadastre-se</a></p>
            <p><a href="/">Voltar ao início</a></p>
        </div>
    </div>
    
    <script>
        async function login() {
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('error');
            const successDiv = document.getElementById('success');
            const spinner = document.getElementById('spinner');
            const loginBtn = document.getElementById('loginBtn');
            
            errorDiv.textContent = '';
            successDiv.textContent = '';
            
            if (!email || !password) {
                errorDiv.textContent = 'Por favor, preencha todos os campos';
                return;
            }
            
            spinner.style.display = 'block';
            loginBtn.disabled = true;
            
            try {
                const response = await fetch('/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email, password })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    successDiv.textContent = 'Login realizado com sucesso! Redirecionando...';
                    localStorage.setItem('token', data.access_token);
                    
                    // Redireciona para a documentação
                    setTimeout(() => {
                        // Adiciona token no header Authorization
                        window.location.href = '/docs';
                    }, 1500);
                } else {
                    errorDiv.textContent = data.detail || 'Erro ao fazer login';
                }
            } catch (error) {
                errorDiv.textContent = 'Erro de conexão. Tente novamente.';
            } finally {
                spinner.style.display = 'none';
                loginBtn.disabled = false;
            }
        }
        
        // Permite login com Enter
        document.getElementById('password').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') login();
        });
        
        document.getElementById('email').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('password').focus();
            }
        });
        
        // Auto-inject token no Swagger UI se existir
        window.addEventListener('load', function() {
            const token = localStorage.getItem('token');
            if (token && window.location.pathname === '/docs') {
                setTimeout(() => {
                    // Tenta injetar o token no Swagger UI
                    const authBtn = document.querySelector('.btn.authorize');
                    if (authBtn) {
                        authBtn.click();
                        setTimeout(() => {
                            const tokenInput = document.querySelector('input[type="text"][placeholder*="Bearer"]');
                            if (tokenInput) {
                                tokenInput.value = token;
                                const authorizeBtn = document.querySelector('.auth-btn-wrapper .btn.modal-btn.auth.authorize');
                                if (authorizeBtn) authorizeBtn.click();
                            }
                        }, 300);
                    }
                }, 1000);
            }
        });
    </script>
</body>
</html>
"""

# Middleware para proteger documentação
class DocsAuthMiddleware(BaseHTTPMiddleware):
    """Middleware para proteger acesso à documentação da API"""
    
    async def dispatch(self, request: Request, call_next):
        # Lista de paths que requerem autenticação
        protected_paths = ["/docs", "/redoc", "/openapi.json"]
        
        # Verifica se o path precisa de autenticação
        if request.url.path in protected_paths:
            # Busca token no header Authorization
            auth = request.headers.get("Authorization")
            
            # Se não tem token, mostra página de login
            if not auth or not auth.startswith("Bearer "):
                if request.url.path in ["/docs", "/redoc"]:
                    return HTMLResponse(content=LOGIN_PAGE_HTML, status_code=200)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token de autenticação necessário",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            
            # Valida token
            token = auth.replace("Bearer ", "")
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                # Token válido, continua
            except jwt.ExpiredSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expirado. Faça login novamente."
                )
            except jwt.PyJWTError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token inválido"
                )
        
        # Continua processamento normal
        response = await call_next(request)
        return response

# Adiciona middleware
app.add_middleware(DocsAuthMiddleware)

# Inclui routers
app.include_router(security_api.router, prefix="/auth", tags=["Autenticação"])
app.include_router(cnpj_router.router, prefix="/api/cnpj", tags=["CNPJ"])
app.include_router(cruzamentos.router, prefix="/api/cruzamentos", tags=["Cruzamentos e Vínculos"])

# ============ ENDPOINTS DA APLICAÇÃO ============

@app.get("/", tags=["Root"])
async def root():
    """Endpoint raiz com informações da API"""
    return {
        "message": "CNPJ API - PostgreSQL",
        "version": "4.0.0",
        "status": "online",
        "endpoints": {
            "auth": {
                "register": "POST /auth/register",
                "login": "POST /auth/login",
                "confirm": "GET /auth/confirm/{token}",
                "refresh": "POST /auth/refresh",
                "me": "GET /auth/me"
            },
            "cnpj": {
                "consultar": "GET /api/cnpj/{cnpj}",
                "por_uf": "GET /api/cnpj/uf/{uf}",
                "por_municipio": "GET /api/cnpj/municipio/{nome_municipio}",
                "por_cnae_principal": "GET /api/cnpj/cnae_principal/{cnae}",
                "por_cnae_secundaria": "GET /api/cnpj/cnae_secundaria/{cnae}",
                "uf_cnae_principal": "GET /api/cnpj/uf/{uf}/cnae_principal/{cnae}",
                "uf_cnae_secundaria": "GET /api/cnpj/uf/{uf}/cnae_secundaria/{cnae}",
                "municipio_cnae_principal": "GET /api/cnpj/municipio/{nome_municipio}/cnae_principal/{cnae}",
                "municipio_cnae_secundaria": "GET /api/cnpj/municipio/{nome_municipio}/cnae_secundaria/{cnae}"
            },
            "cruzamentos": {
                "enderecos_compartilhados": "GET /api/cruzamentos/enderecos/compartilhados",
                "emails_compartilhados": "GET /api/cruzamentos/emails/compartilhados",
                "telefones_compartilhados": "GET /api/cruzamentos/telefones/compartilhados",
                "enderecos_duplicados": "GET /api/cruzamentos/enderecos/duplicados",
                "telefones_duplicados": "GET /api/cruzamentos/telefones/duplicados",
                "emails_duplicados": "GET /api/cruzamentos/emails/duplicados",
                "vinculos": "GET /api/cruzamentos/vinculos/{cnpj}",
                "rede": "GET /api/cruzamentos/rede/{cnpj}",
                "grupo_economico": "GET /api/cruzamentos/analise/grupo_economico/{cnpj}"
            }
        },
        "docs": "/docs (requer autenticação)",
        "redoc": "/redoc (requer autenticação)",
        "health": "/health",
        "stats": "/stats"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Verifica o status da API e banco de dados"""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    
    try:
        # Configuração do banco
        DB_USER = os.getenv("DB_USER", "admin")
        DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = os.getenv("DB_PORT", "5432")
        DB_NAME = os.getenv("DB_NAME", "cnpj_rede")
        
        DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        engine = create_async_engine(DATABASE_URL)
        
        async with engine.begin() as conn:
            # Testa conexão e conta registros
            result = await conn.execute(text("""
                SELECT 
                    (SELECT COUNT(*) FROM cnpj.empresas) as empresas,
                    (SELECT COUNT(*) FROM cnpj.estabelecimento) as estabelecimentos,
                    (SELECT COUNT(*) FROM cnpj.socios) as socios,
                    (SELECT COUNT(*) FROM security.users) as usuarios,
                    (SELECT COUNT(*) FROM rede.ligacao) as ligacoes,
                    (SELECT COUNT(*) FROM links.link_ete) as links_ete
            """))
            counts = result.first()
        
        await engine.dispose()
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "statistics": {
                "empresas": counts[0] if counts else 0,
                "estabelecimentos": counts[1] if counts else 0,
                "socios": counts[2] if counts else 0,
                "usuarios": counts[3] if counts else 0,
                "ligacoes": counts[4] if counts else 0,
                "links_ete": counts[5] if counts else 0
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        )

@app.get("/stats", tags=["Statistics"])
async def get_statistics(user: dict = Depends(get_current_user)):
    """Retorna estatísticas detalhadas do banco de dados"""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    
    DB_USER = os.getenv("DB_USER", "admin")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "cnpj_rede")
    
    DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        # Estatísticas gerais
        result = await conn.execute(text("""
            SELECT 
                (SELECT COUNT(*) FROM cnpj.empresas) as total_empresas,
                (SELECT COUNT(*) FROM cnpj.estabelecimento) as total_estabelecimentos,
                (SELECT COUNT(*) FROM cnpj.estabelecimento WHERE matriz_filial = '1') as total_matrizes,
                (SELECT COUNT(*) FROM cnpj.estabelecimento WHERE matriz_filial = '2') as total_filiais,
                (SELECT COUNT(*) FROM cnpj.estabelecimento WHERE situacao_cadastral = '02') as estabelecimentos_ativos,
                (SELECT COUNT(*) FROM cnpj.socios) as total_socios,
                (SELECT COUNT(DISTINCT cnpj_cpf_socio) FROM cnpj.socios WHERE LENGTH(cnpj_cpf_socio) = 11) as total_pf_socios,
                (SELECT COUNT(DISTINCT cnpj_cpf_socio) FROM cnpj.socios WHERE LENGTH(cnpj_cpf_socio) = 14) as total_pj_socios,
                (SELECT COUNT(*) FROM rede.ligacao) as total_ligacoes,
                (SELECT COUNT(*) FROM links.link_ete WHERE descricao = 'end') as total_enderecos_compartilhados,
                (SELECT COUNT(*) FROM links.link_ete WHERE descricao = 'tel') as total_telefones_compartilhados,
                (SELECT COUNT(*) FROM links.link_ete WHERE descricao = 'email') as total_emails_compartilhados,
                (SELECT COUNT(*) FROM security.users) as total_usuarios,
                (SELECT COUNT(*) FROM security.users WHERE is_active = 0) as usuarios_free,
                (SELECT COUNT(*) FROM security.users WHERE is_active = 1) as usuarios_pagos,
                (SELECT COUNT(*) FROM security.users WHERE is_active = 2) as usuarios_ilimitados
        """))
        stats = result.first()
        
        # Data de referência
        result = await conn.execute(text("""
            SELECT valor FROM cnpj.referencia WHERE referencia = 'data_atualizacao'
        """))
        data_ref = result.first()
    
    await engine.dispose()
    
    return {
        "estatisticas_gerais": {
            "total_empresas": stats[0] if stats else 0,
            "total_estabelecimentos": stats[1] if stats else 0,
            "total_matrizes": stats[2] if stats else 0,
            "total_filiais": stats[3] if stats else 0,
            "estabelecimentos_ativos": stats[4] if stats else 0,
            "total_socios": stats[5] if stats else 0,
            "socios_pessoa_fisica": stats[6] if stats else 0,
            "socios_pessoa_juridica": stats[7] if stats else 0
        },
        "estatisticas_rede": {
            "total_ligacoes": stats[8] if stats else 0,
            "enderecos_compartilhados": stats[9] if stats else 0,
            "telefones_compartilhados": stats[10] if stats else 0,
            "emails_compartilhados": stats[11] if stats else 0
        },
        "estatisticas_usuarios": {
            "total": stats[12] if stats else 0,
            "plano_gratuito": stats[13] if stats else 0,
            "plano_pago": stats[14] if stats else 0,
            "plano_ilimitado": stats[15] if stats else 0
        },
        "data_referencia": data_ref[0] if data_ref else None,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# ============ TRATAMENTO DE ERROS ============

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Endpoint não encontrado",
            "path": request.url.path,
            "method": request.method,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(422)
async def validation_error_handler(request: Request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Erro de validação",
            "details": str(exc),
            "path": request.url.path,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"Internal error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Erro interno do servidor",
            "message": "Por favor, tente novamente mais tarde",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
    )

# ============ EVENTOS DE STARTUP E SHUTDOWN ============

@app.on_event("startup")
async def startup_event():
    """Executa ao iniciar a aplicação"""
    logger.info("=" * 60)
    logger.info("🚀 CNPJ API - PostgreSQL iniciando...")
    logger.info(f"📍 Banco de dados: {os.getenv('DB_NAME', 'cnpj_rede')}")
    logger.info(f"🌐 Host: {os.getenv('API_HOST', '0.0.0.0')}")
    logger.info(f"🔌 Porta: {os.getenv('API_PORT', '8430')}")
    logger.info("=" * 60)
    
    # Verifica conexão com banco
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        
        DB_USER = os.getenv("DB_USER", "admin")
        DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = os.getenv("DB_PORT", "5432")
        DB_NAME = os.getenv("DB_NAME", "cnpj_rede")
        
        DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        engine = create_async_engine(DATABASE_URL)
        
        async with engine.begin() as conn:
            # Verifica schemas
            result = await conn.execute(text("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name IN ('cnpj', 'rede', 'links', 'security')
                ORDER BY schema_name
            """))
            schemas = [row[0] for row in result.fetchall()]
            
            if len(schemas) < 4:
                logger.warning(f"⚠️ Schemas faltando. Encontrados: {schemas}")
                logger.warning("⚠️ Execute o script de importação para criar os schemas necessários")
            else:
                logger.info(f"✅ Todos os schemas encontrados: {schemas}")
            
            # Verifica tabelas principais
            result = await conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = 'cnpj' 
                AND table_name IN ('empresas', 'estabelecimento', 'socios')
            """))
            table_count = result.scalar()
            
            if table_count < 3:
                logger.warning("⚠️ Tabelas principais não encontradas no schema cnpj")
            else:
                logger.info(f"✅ Tabelas principais verificadas")
        
        await engine.dispose()
        logger.info("✅ Conexão com banco de dados estabelecida")
        
    except Exception as e:
        logger.error(f"❌ Erro ao conectar com banco de dados: {e}")
        logger.error("❌ A API iniciará mas pode apresentar erros")
        logger.error("💡 Verifique as configurações no arquivo .env")

@app.on_event("shutdown")
async def shutdown_event():
    """Executa ao desligar a aplicação"""
    logger.info("=" * 60)
    logger.info("👋 CNPJ API encerrando...")
    logger.info("=" * 60)

# ============ MAIN ============

if __name__ == "__main__":
    import uvicorn
    
    # Configurações do servidor
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8430"))
    
    # Inicia servidor
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,  # Desabilite em produção
        log_level="info",
        access_log=True
    )