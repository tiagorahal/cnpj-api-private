import streamlit as st
import pandas as pd
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Carrega variáveis .env
load_dotenv()

DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cnpj_rede")
DATABASE_AUTH = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_AUTH)
SessionLocal = sessionmaker(bind=engine)

st.set_page_config(page_title="Painel Admin - Usuários", layout="wide")
st.title("👤 Painel Admin - Gerenciar Usuários")

def fetch_users():
    with SessionLocal() as session:
        result = session.execute(
            text("SELECT id, email, is_active, email_confirmed FROM security.users ORDER BY id")
        )
        users = result.fetchall()
    return [dict(row._mapping) for row in users]

def update_status(user_id, new_status):
    with SessionLocal() as session:
        session.execute(
            text("UPDATE security.users SET is_active = :is_active WHERE id = :id"),
            {"is_active": new_status, "id": user_id}
        )
        session.commit()

def status_str(code):
    return {0: "Gratuito", 1: "Pago", 2: "Ilimitado"}.get(code, f"Desconhecido ({code})")

if "users" not in st.session_state:
    st.session_state["users"] = fetch_users()

users = st.session_state["users"]

if not users:
    st.warning("Nenhum usuário encontrado!")
else:
    df = pd.DataFrame(users)
    df["Plano"] = df["is_active"].apply(status_str)
    df["Email Confirmado"] = df["email_confirmed"].map({0: "Não", 1: "Sim"})

    st.dataframe(df[["id", "email", "Plano", "Email Confirmado"]], hide_index=True)

    st.markdown("---")
    st.subheader("Alterar Status de Usuário")

    user_options = {f'{u["email"]} (id={u["id"]})': u["id"] for u in users}
    user_select = st.selectbox("Selecione o usuário:", list(user_options.keys()))
    user_id = user_options[user_select]

    current_status = [u for u in users if u["id"] == user_id][0]["is_active"]
    new_status = st.selectbox(
        "Novo status:",
        options=[0, 1, 2],
        format_func=status_str,
        index=current_status
    )

    if st.button("Atualizar Status"):
        update_status(user_id, new_status)
        st.success("Status atualizado! Recarregue a página para ver a mudança.")
        st.session_state["users"] = fetch_users()

    st.info("0 = Gratuito | 1 = Pago | 2 = Ilimitado")
