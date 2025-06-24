#!/bin/bash

echo "[*] Executando dados_cnpj_baixa.py ..."
python3 dados_cnpj_baixa.py

echo "[*] Aguardando 3 segundos..."
sleep 3

echo "[*] Executando dados_cnpj_para_sqlite.py ..."
python3 dados_cnpj_para_sqlite.py

echo "[*] Aguardando 3 segundos..."
sleep 3

echo "[*] Executando rede_cria_tabela_cnpj_links_ete.py ..."
python3 rede_cria_tabela_cnpj_links_ete.py

echo "[✓] Processo concluído!"
