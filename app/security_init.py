"""
Script para criar tabelas de segurança/autenticação no PostgreSQL
Cria no schema 'security' dentro do banco cnpj_rede
"""

import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cnpj_rede")  # Banco único

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, future=True)

async def init_db():
    async with engine.begin() as conn:
        # Criar schema security se não existir
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS security"))
        
        # Se quiser resetar a tabela, descomente:
        # await conn.execute(text("DROP TABLE IF EXISTS security.users CASCADE"))
        
        # Criar tabela de usuários
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS security.users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email_confirmed INTEGER DEFAULT 0,
                confirmation_token TEXT,
                refresh_token TEXT,
                is_active INTEGER DEFAULT 0,
                request_count INTEGER DEFAULT 0,
                last_request_date DATE,
                monthly_request_count INTEGER DEFAULT 0,
                last_request_month VARCHAR(7),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Criar índices
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_email ON security.users(email)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_confirmation_token ON security.users(confirmation_token)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_is_active ON security.users(is_active)"))

        
        # Criar tabela de logs de acesso (opcional)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS security.access_logs (
                id SERIAL PRIMARY KEY,
                user_email TEXT,
                endpoint TEXT,
                method TEXT,
                status_code INTEGER,
                response_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        print("✅ Tabelas de segurança criadas/garantidas no schema 'security'")
        print(f"📍 Banco de dados: {DB_NAME}")
        print(f"📍 Schema: security")

if __name__ == "__main__":
    asyncio.run(init_db())