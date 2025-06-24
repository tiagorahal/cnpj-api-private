import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import uvicorn

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME_SECURITY = os.getenv("DB_NAME_SECURITY")

DATABASE_AUTH = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME_SECURITY}"

engine = create_async_engine(DATABASE_AUTH, future=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    async with async_session() as session:
        result = await session.execute(text("SELECT id, email, is_active FROM users"))
        users = result.fetchall()
    # users é uma lista de Row, então convertemos para dict para usar no Jinja
    users_list = [dict(row._mapping) for row in users]
    return templates.TemplateResponse("dashboard.html", {"request": request, "users": users_list})

@app.post("/toggle")
async def toggle_user(id: int = Form(...), is_active: int = Form(...)):
    async with async_session() as session:
        await session.execute(
            text("UPDATE users SET is_active = :is_active WHERE id = :id"),
            {"is_active": is_active, "id": id}
        )
        await session.commit()
    return RedirectResponse("/", status_code=303)

if __name__ == "__main__":
    uvicorn.run("dashboard:app", host="0.0.0.0", port=10005, reload=True)
