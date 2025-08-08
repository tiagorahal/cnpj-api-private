import streamlit as st
import requests
import pandas as pd
import re
from io import BytesIO

API_URL = "http://localhost:8430"

st.set_page_config(page_title="CNPJ API Test Front", layout="wide")
st.title("🔗 CNPJ API - Interface de Teste")

def clean_cnpj(val):
    return re.sub(r'\D', '', val or '')

with st.expander("🔐 Login", expanded=True):
    email = st.text_input("Email", value="admin@email.com")
    password = st.text_input("Senha", type="password", value="123456")
    login_btn = st.button("Entrar")

    if "token" not in st.session_state:
        st.session_state.token = None

    if login_btn:
        resp = requests.post(f"{API_URL}/auth/login", json={"email": email, "password": password})
        if resp.ok:
            st.session_state.token = resp.json()["access_token"]
            st.success("Login realizado com sucesso!")
        else:
            st.error(resp.json().get("detail", "Erro no login."))

if not st.session_state.token:
    st.warning("Faça login para acessar os endpoints.")
    st.stop()

headers = {"Authorization": f"Bearer {st.session_state.token}"}

st.header("Endpoints Disponíveis")
endpoint_group = st.selectbox(
    "Selecione a categoria:",
    ["CNPJ", "Cruzamentos", "Usuário/Autenticação"]
)

endpoints = {
    "CNPJ": [
        ("/api/cnpj/{cnpj}", "Consulta CNPJ", ["cnpj"]),
        ("/api/cnpj/uf/{uf}", "Listar por UF", ["uf", "page"]),
        ("/api/cnpj/municipio/{nome_municipio}", "Listar por município", ["nome_municipio", "page"]),
        ("/api/cnpj/cnae_principal/{cnae}", "Por CNAE principal", ["cnae", "page"]),
        ("/api/cnpj/cnae_secundaria/{cnae}", "Por CNAE secundária", ["cnae", "page"]),
        ("/api/cnpj/uf/{uf}/cnae_principal/{cnae}", "Por UF + CNAE principal", ["uf", "cnae", "page"]),
        ("/api/cnpj/uf/{uf}/cnae_secundaria/{cnae}", "Por UF + CNAE secundária", ["uf", "cnae", "page"]),
        ("/api/cnpj/municipio/{nome_municipio}/cnae_principal/{cnae}", "Por município + CNAE principal", ["nome_municipio", "cnae", "page"]),
        ("/api/cnpj/municipio/{nome_municipio}/cnae_secundaria/{cnae}", "Por município + CNAE secundária", ["nome_municipio", "cnae", "page"]),
    ],
    "Cruzamentos": [
        ("/api/cruzamentos/enderecos/compartilhados", "Endereços compartilhados", ["endereco"]),
        ("/api/cruzamentos/emails/compartilhados", "Emails compartilhados", ["email"]),
        ("/api/cruzamentos/telefones/compartilhados", "Telefones compartilhados", ["ddd", "telefone"]),
        ("/api/cruzamentos/enderecos/duplicados", "Endereços duplicados", ["minimo", "limite"]),
        ("/api/cruzamentos/telefones/duplicados", "Telefones duplicados", ["minimo", "limite"]),
        ("/api/cruzamentos/emails/duplicados", "Emails duplicados", ["minimo", "limite"]),
        ("/api/cruzamentos/vinculos/{cnpj}", "Vínculos do CNPJ", ["cnpj"]),
        ("/api/cruzamentos/rede/{cnpj}", "Rede do CNPJ", ["cnpj", "nivel"]),
        ("/api/cruzamentos/analise/grupo_economico/{cnpj}", "Grupo econômico", ["cnpj"]),
    ],
    "Usuário/Autenticação": [
        ("/auth/me", "Meus Dados", []),
        ("/auth/refresh", "Refresh Token", []),
    ]
}

selected = st.selectbox(
    "Escolha o endpoint:",
    endpoints[endpoint_group],
    format_func=lambda x: f"{x[1]}  [{x[0]}]"
)
endpoint, desc, params = selected

st.write(f"**{desc}**")
input_data = {}

for param in params:
    default = "" if param not in ("page", "minimo", "limite", "nivel") else 1
    val = st.text_input(param, value=default)
    if "cnpj" in param.lower():
        val = clean_cnpj(val)
    if param.lower() == "uf":
        val = val.upper()
    input_data[param] = val

run_btn = st.button("Executar Consulta")
response_data = None

def make_request():
    url = API_URL + endpoint
    for param in params:
        if "{" + param + "}" in url:
            url = url.replace("{" + param + "}", str(input_data[param]))
    qparams = {k: v for k, v in input_data.items() if "{" + k + "}" not in endpoint}
    method = "get"
    if endpoint == "/auth/refresh":
        method = "post"
        qparams = {"current_token": st.session_state.token}
    if method == "get":
        r = requests.get(url, params=qparams, headers=headers)
    else:
        r = requests.post(url, json=qparams, headers=headers)
    return r

if run_btn:
    r = make_request()
    try:
        if r.ok:
            response_data = r.json()
            st.success("Consulta realizada com sucesso!")
            st.json(response_data)
            st.session_state["last_response"] = response_data
        else:
            try:
                err = r.json()
            except Exception:
                err = r.text
            st.error(f"Erro {r.status_code}: {err}")
    except Exception as e:
        st.error(f"Erro inesperado: {e}")

# ------------------ Exportar Planilha ------------------

from io import BytesIO

if "last_response" in st.session_state and st.session_state["last_response"]:
    st.markdown("### Exportar resultado para Excel")
    resp = st.session_state["last_response"]
    buffer = BytesIO()
    wrote_excel = False

    # Consulta CNPJ única: mostra empresa e sócios
    if isinstance(resp, dict) and "empresa" in resp and "socios" in resp:
        empresa_df = pd.DataFrame([resp["empresa"]])
        socios_df = pd.DataFrame(resp["socios"])
        st.subheader("Empresa")
        st.dataframe(empresa_df)
        st.subheader("Sócios")
        st.dataframe(socios_df)
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            empresa_df.to_excel(writer, index=False, sheet_name="Empresa")
            socios_df.to_excel(writer, index=False, sheet_name="Socios")
        wrote_excel = True
    # Outros casos: lista única
    else:
        to_df = None
        if isinstance(resp, dict):
            for key in ["resultado", "enderecos_duplicados", "telefones_duplicados", "emails_duplicados", "enderecos", "cnpjs", "dados"]:
                if key in resp and isinstance(resp[key], list):
                    to_df = pd.DataFrame(resp[key])
                    break
            if to_df is None:
                for v in resp.values():
                    if isinstance(v, list):
                        to_df = pd.DataFrame(v)
                        break
        elif isinstance(resp, list):
            to_df = pd.DataFrame(resp)
        else:
            to_df = pd.DataFrame([resp])
        if to_df is not None:
            st.dataframe(to_df)
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                to_df.to_excel(writer, index=False, sheet_name="Dados")
            wrote_excel = True

    if wrote_excel:
        buffer.seek(0)
        st.download_button(
            label="Baixar Excel",
            data=buffer,
            file_name="resultado_cnpj_api.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("Não foi possível converter a resposta em tabela.")
