# Makefile para CNPJ API
.PHONY: help build up down clean logs shell db-shell reset full-setup quick-start status backup restore

# Cores para output
RED=\033[0;31m
GREEN=\033[0;32m
YELLOW=\033[1;33m
NC=\033[0m # No Color

help: ## Mostra esta mensagem de ajuda
	@echo "$(GREEN)CNPJ API - Comandos Disponíveis$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'

# ========== COMANDOS PRINCIPAIS ==========
super-setup:
	@echo "🛠️  Resetando Docker e rebuildando tudo do zero..."
	docker compose down -v
	docker compose build --no-cache
	docker compose up -d db
	@echo "⏳ Aguardando banco de dados iniciar..."
	sleep 15  # tempo para o banco iniciar, ajuste se precisar
	docker compose run --rm importer
	docker compose up -d api streamlit
	@echo "✅ Setup completo! API e Streamlit rodando."

full-setup: ## Setup completo: baixa dados da Receita e importa no PostgreSQL (demora horas!)
	@echo "$(YELLOW)🚀 Iniciando setup completo do CNPJ API$(NC)"
	@echo "$(RED)⚠️  ATENÇÃO: Este processo pode demorar 4-6 horas!$(NC)"
	@echo "$(RED)⚠️  Serão baixados ~5GB de dados e ocupará ~50GB após importação$(NC)"
	@read -p "Deseja continuar? (y/N) " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose up -d db
	@echo "$(GREEN)Aguardando PostgreSQL...$(NC)"
	@sleep 10
	docker compose up importer
	docker compose up -d api streamlit
	@echo "$(GREEN)✅ Setup completo finalizado!$(NC)"
	@echo "API: http://localhost:8430/docs"
	@echo "Streamlit: http://localhost:8501"
	@echo "Login: admin@cnpj.com / admin123"

quick-start: ## Inicia rapidamente com dados de teste (sem download da Receita)
	@echo "$(YELLOW)🚀 Iniciando CNPJ API com dados de teste$(NC)"
	docker compose up -d db
	@sleep 10
	docker compose exec db psql -U admin -d cnpj_rede -f /docker-entrypoint-initdb.d/init.sql
	docker compose run --rm api python /app/init_admin.py
	docker compose up -d api streamlit
	@echo "$(GREEN)✅ API iniciada com dados de teste!$(NC)"
	@echo "API: http://localhost:8430/docs"
	@echo "Streamlit: http://localhost:8501"
	@echo "Login: admin@cnpj.com / admin123"

# ========== COMANDOS DE BUILD ==========

build: ## Builda todas as imagens
	docker compose build

build-nocache: ## Builda sem cache
	docker compose build --no-cache

# ========== COMANDOS DE EXECUÇÃO ==========

up: ## Sobe todos os serviços
	docker compose up -d

down: ## Para todos os serviços
	docker compose down

restart: ## Reinicia todos os serviços
	docker compose restart

# ========== COMANDOS ESPECÍFICOS ==========

api: ## Sobe apenas a API
	docker compose up -d db
	@sleep 5
	docker compose up -d api

streamlit: ## Sobe apenas o Streamlit
	docker compose up -d api
	docker compose up -d streamlit

db: ## Sobe apenas o banco de dados
	docker compose up -d db

import-only: ## Executa apenas a importação (dados já baixados)
	SKIP_DOWNLOAD=true docker compose up importer

download-only: ## Executa apenas o download (sem importar)
	SKIP_IMPORT=true docker compose up importer

# ========== COMANDOS DE MANUTENÇÃO ==========

logs: ## Mostra logs de todos os serviços
	docker compose logs -f

logs-api: ## Mostra logs da API
	docker compose logs -f api

logs-db: ## Mostra logs do banco
	docker compose logs -f db

logs-import: ## Mostra logs do importador
	docker compose logs -f importer

status: ## Mostra status dos containers
	@docker compose ps

shell: ## Abre shell no container da API
	docker compose exec api bash

db-shell: ## Abre psql no banco
	docker compose exec db psql -U admin -d cnpj_rede

clean: ## Remove containers e volumes (CUIDADO: apaga todos os dados!)
	@echo "$(RED)⚠️  ATENÇÃO: Isso apagará TODOS os dados!$(NC)"
	@read -p "Tem certeza? (y/N) " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose down -v
	rm -rf logs/*.log

reset: clean ## Reset completo: remove tudo e reconstrói
	docker compose build --no-cache
	@echo "$(GREEN)✅ Reset completo realizado!$(NC)"

# ========== BACKUP E RESTORE ==========

backup: ## Faz backup do banco de dados
	@mkdir -p backups
	@BACKUP_FILE="backups/cnpj_backup_$$(date +%Y%m%d_%H%M%S).sql"
	docker compose exec -T db pg_dump -U admin cnpj_rede > $$BACKUP_FILE
	@echo "$(GREEN)✅ Backup salvo em: $$BACKUP_FILE$(NC)"

restore: ## Restaura backup do banco (uso: make restore FILE=backups/arquivo.sql)
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED)Erro: especifique o arquivo. Ex: make restore FILE=backups/arquivo.sql$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Restaurando backup de $(FILE)...$(NC)"
	docker compose exec -T db psql -U admin cnpj_rede < $(FILE)
	@echo "$(GREEN)✅ Backup restaurado!$(NC)"

# ========== DESENVOLVIMENTO ==========

dev: ## Modo desenvolvimento com hot-reload
	docker compose -f docker compose.yml -f docker compose.dev.yml up

test-import: ## Testa importação com dados pequenos
	docker compose run --rm importer python -c "print('Teste de importação')"

# ========== MONITORAMENTO ==========

stats: ## Mostra estatísticas do banco
	@docker compose exec db psql -U admin -d cnpj_rede -c "\
		SELECT \
			schema_name, \
			COUNT(*) as tables, \
			pg_size_pretty(SUM(pg_total_relation_size(schemaname||'.'||tablename))::bigint) as size \
		FROM information_schema.tables t \
		JOIN pg_tables pt ON t.table_name = pt.tablename \
		WHERE schema_name IN ('cnpj', 'rede', 'links', 'security') \
		GROUP BY schema_name;"

disk-usage: ## Mostra uso de disco
	@docker system df
	@echo ""
	@docker compose exec db df -h /var/lib/postgresql/data