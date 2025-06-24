import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME_SECURITY = os.getenv("DB_NAME_SECURITY")

DATABASE_AUTH = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME_SECURITY}"

engine = create_async_engine(DATABASE_AUTH, future=True)

async def init_db():
    async with engine.begin() as conn:
        # Se quiser resetar a tabela, descomente a linha abaixo:
        # await conn.execute(text("DROP TABLE IF EXISTS users"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email_confirmed INTEGER DEFAULT 0,
                confirmation_token TEXT,
                refresh_token TEXT,
                is_active INTEGER DEFAULT 0
            )
        """))
        print("Tabela 'users' criada/garantida no banco de dados.")

asyncio.run(init_db())
