#!/bin/bash
# start_all.sh

# 1. Sobe o PostgreSQL
sudo service postgresql start

# 2. Ativa o venv se usar virtualenv (descomente se usar)
# source ~/code/cnpj-api-private/venv/bin/activate

# 3. Sobe a API FastAPI (em background, log para arquivo logs/uvicorn.log)
cd ~/code/cnpj-api-private
mkdir -p logs
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8430 \
  --workers 12 \
  --limit-concurrency 20 \
  --http httptools \
  --loop uvloop \
  --timeout-keep-alive 5 \
  > logs/uvicorn.log 2>&1 &

# 4. Sobe o painel streamlit (em background, log para logs/streamlit.log)
cd ~/code/cnpj-api-private/app
streamlit run streamlit_app.py > ../logs/streamlit.log 2>&1 &

# 5. Sobe admin_streamlit.py (em background, log para logs/admin_streamlit.log)
streamlit run admin_streamlit.py > ../logs/admin_streamlit.log 2>&1 &

echo "Tudo iniciado! (Procure logs na pasta logs/)"
