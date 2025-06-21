import asyncio
import aiosqlite
import os
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME_SECURITY = os.getenv("DB_NAME_SECURITY")

DATABASE_AUTH = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME_SECURITY}"

async def ver_quantidade_requests(email_usuario: str):
    async with aiosqlite.connect(DATABASE_AUTH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT email, is_active, request_count, last_request_date, monthly_request_count, last_request_month FROM users WHERE email = ?", (email_usuario,))
        user = await cursor.fetchone()
        await cursor.close()

        if not user:
            print(f"Usuário '{email_usuario}' não encontrado.")
            return

        print(f"Usuário: {user['email']}")
        print(f"Status (is_active): {user['is_active']}")
        print(f"Requisições hoje ({user['last_request_date']}): {user['request_count']}")
        print(f"Requisições mês ({user['last_request_month']}): {user['monthly_request_count']}")

if __name__ == "__main__":
    email = input("Digite o email do usuário para verificar: ")
    asyncio.run(ver_quantidade_requests(email))
