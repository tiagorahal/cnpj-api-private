#!/bin/bash
# stop_all.sh

# Mata todos os processos que iniciamos
pkill -f "uvicorn app.main:app"
pkill -f "streamlit run streamlit_app.py"
pkill -f "admin_streamlit.py"

# Opcional: para o PostgreSQL se quiser
# sudo service postgresql stop

echo "Tudo parado!"
