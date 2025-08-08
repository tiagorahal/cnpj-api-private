#!/bin/bash
# start_all.sh

# 1. Sobe o PostgreSQL
sudo service postgresql start

# 2. Ativa o venv se usar virtualenv (descomente se usar)
# source ~/code/cnpj-api-private/venv/bin/activate

# 3. Sobe a API FastAPI (em background, log para arquivo)
cd ~/code/cnpj-api-private
uvicorn app.main:app --host 0.0.0.0 --port 8430 --workers 4 > uvicorn.log 2>&1 &

# 4. Sobe o painel streamlit (em background)
cd ~/code/cnpj-api-private/app
streamlit run streamlit_app.py > streamlit.log 2>&1 &

# 5. Sobe admin_streamlit.py (em background)
streamlit run admin_streamlit.py > admin_streamlit.log 2>&1 &

echo "Tudo iniciado! (Procure logs em *.log)"
