import aiosqlite
import asyncio
import os

DATABASE_PATH = "database/security.db"

async def init_db():
    if os.path.exists(DATABASE_PATH):
        os.remove(DATABASE_PATH)
        print("Banco antigo removido.")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email_confirmed INTEGER DEFAULT 0,
                confirmation_token TEXT,
                refresh_token TEXT,
                is_active INTEGER DEFAULT 0
            )
        """)
        await db.commit()
        print("Novo banco criado com sucesso.")

asyncio.run(init_db())
