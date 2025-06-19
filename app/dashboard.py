import aiosqlite
import os
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn

# Caminho absoluto para o banco de dados, compatível em produção e debug
DATABASE_AUTH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../database/security.db")
)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    async with aiosqlite.connect(DATABASE_AUTH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, email, is_active FROM users")
        users = await cursor.fetchall()
        await cursor.close()
    # Passa os usuários para o template normalmente
    return templates.TemplateResponse("dashboard.html", {"request": request, "users": users})

@app.post("/toggle")
async def toggle_user(id: int = Form(...), is_active: int = Form(...)):
    # Agora seta exatamente o valor recebido do formulário
    async with aiosqlite.connect(DATABASE_AUTH) as db:
        await db.execute("UPDATE users SET is_active = ? WHERE id = ?", (is_active, id))
        await db.commit()
    return RedirectResponse("/", status_code=303)

if __name__ == "__main__":
    uvicorn.run("dashboard:app", host="0.0.0.0", port=10005, reload=True)
