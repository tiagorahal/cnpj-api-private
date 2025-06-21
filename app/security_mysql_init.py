import aiosqlite
import os
import asyncio

DATABASE_AUTH = "database/security.db"

async def init_db():
    # Remove o banco antigo se quiser resetar
    if os.path.exists(DATABASE_AUTH):
        os.remove(DATABASE_AUTH)
        print("Banco antigo removido.")

    async with aiosqlite.connect(DATABASE_AUTH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
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
        print("Tabela 'users' criada/garantida no banco SQLite.")

asyncio.run(init_db())
