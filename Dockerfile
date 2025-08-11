# ================================
# Stage 1: Importer - Download e Importação de Dados
# ================================
FROM python:3.11-slim as importer

# Instala dependências do sistema necessárias
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    postgresql-client \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Cria diretórios necessários
RUN mkdir -p /scripts /dados-publicos /dados-publicos-zip /logs

WORKDIR /scripts

# Copia requirements e instala dependências Python
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copia scripts de download e importação
COPY database/scripts/dados_cnpj_baixa.py /scripts/
COPY database/scripts/import_cnpj_postgresql.py /scripts/

# Cria script Python para corrigir os caminhos
COPY <<'FIXPATHS' /scripts/fix_paths.py
#!/usr/bin/env python3
import sys
import re

def fix_paths(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    replacements = [
        ('../dados-publicos-zip', '/dados-publicos-zip'),
        ('../dados-publicos', '/dados-publicos'),
        ('../dados_publicos_zip', '/dados-publicos-zip'),
        ('../dados_publicos', '/dados-publicos'),
    ]
    
    for old, new in replacements:
        content = content.replace(f"'{old}'", f"'{new}'")
        content = content.replace(f'"{old}"', f'"{new}"')
        content = content.replace(f"f'{old}", f"f'{new}")
        content = content.replace(f'f"{old}', f'f"{new}')
    
    with open(filename, 'w') as f:
        f.write(content)
    print(f"✅ Caminhos corrigidos em {filename}")

if __name__ == "__main__":
    try:
        fix_paths('/scripts/dados_cnpj_baixa.py')
        fix_paths('/scripts/import_cnpj_postgresql.py')
    except Exception as e:
        print(f"❌ Erro ao corrigir caminhos: {e}")
        sys.exit(1)
FIXPATHS

RUN python3 /scripts/fix_paths.py

# Script de entrada para o importer
COPY <<'ENTRYPOINT' /scripts/entrypoint.sh
#!/bin/bash
set -e

echo "========================================="
echo "🚀 CNPJ Importer - Iniciando"
echo "========================================="

export PGPASSWORD=$PG_PASSWORD

echo "🔍 Verificando conexão com PostgreSQL..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if psql -h "$PG_HOST" -U "$PG_USER" -d "$PG_DATABASE" -c '\q' 2>/dev/null; then
        echo "✅ PostgreSQL está pronto!"
        break
    fi
    echo "⏳ Tentativa $((attempt+1))/$max_attempts - PostgreSQL não está pronto. Aguardando..."
    sleep 5
    attempt=$((attempt+1))
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ PostgreSQL não respondeu após $max_attempts tentativas"
    exit 1
fi

echo "📦 Criando schemas..."
psql -h "$PG_HOST" -U "$PG_USER" -d "$PG_DATABASE" << SQL
CREATE SCHEMA IF NOT EXISTS cnpj;
CREATE SCHEMA IF NOT EXISTS rede;
CREATE SCHEMA IF NOT EXISTS links;
CREATE SCHEMA IF NOT EXISTS security;
SQL

if [ "$SKIP_DOWNLOAD" != "true" ]; then
    echo "📥 Baixando dados da Receita Federal..."
    cd /scripts
    echo "y" | python3 dados_cnpj_baixa.py
    
    if [ $? -ne 0 ]; then
        echo "❌ Erro no download dos dados"
        tail -n 50 /logs/*.log 2>/dev/null || true
        exit 1
    fi
    echo "✅ Download concluído!"
else
    echo "⏭️ Pulando download (SKIP_DOWNLOAD=true)"
fi

if [ "$SKIP_IMPORT" != "true" ]; then
    echo "📊 Importando dados para PostgreSQL..."
    cd /scripts
    echo "y" | python3 import_cnpj_postgresql.py
    
    if [ $? -ne 0 ]; then
        echo "❌ Erro na importação dos dados"
        tail -n 50 /logs/*.log 2>/dev/null || true
        exit 1
    fi
    echo "✅ Importação concluída!"
else
    echo "⏭️ Pulando importação (SKIP_IMPORT=true)"
fi

touch /dados-publicos/.import_complete

echo "========================================="
echo "✅ Processo completo finalizado!"
echo "========================================="

if [ "$DEBUG_MODE" = "true" ]; then
    echo "🔍 Modo debug ativado. Container permanecerá ativo."
    tail -f /dev/null
fi
ENTRYPOINT

RUN chmod +x /scripts/entrypoint.sh

ENTRYPOINT ["/scripts/entrypoint.sh"]

# ================================
# Stage 2: Runtime - API e Streamlit
# ================================
FROM python:3.11-slim as runtime

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copia código da aplicação
COPY app/ /app/app/

# Cria arquivo .env vazio se não existir
RUN touch /app/.env

# Cria diretórios necessários
RUN mkdir -p /logs /dados-publicos

# Script de inicialização para criar usuário admin
COPY <<'ADMINSCRIPT' /app/init_admin.py
#!/usr/bin/env python3
import os
import sys
import time

def create_admin_user():
    max_attempts = 10
    attempt = 0
    
    time.sleep(5)
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import bcrypt
    except ImportError as e:
        print(f"⚠️ Instalando módulos necessários...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary", "bcrypt"])
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import bcrypt
    
    while attempt < max_attempts:
        try:
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "db"),
                port=os.getenv("DB_PORT", "5432"),
                database=os.getenv("DB_NAME", "cnpj_rede"),
                user=os.getenv("DB_USER", "admin"),
                password=os.getenv("DB_PASSWORD", "admin123")
            )
            cur = conn.cursor()
            
            cur.execute("CREATE SCHEMA IF NOT EXISTS security")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS security.users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    email_confirmed INTEGER DEFAULT 1,
                    confirmation_token TEXT,
                    refresh_token TEXT,
                    is_active INTEGER DEFAULT 2,
                    request_count INTEGER DEFAULT 0,
                    last_request_date DATE,
                    monthly_request_count INTEGER DEFAULT 0,
                    last_request_month VARCHAR(7),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("SELECT email FROM security.users WHERE email = %s", ('admin@cnpj.com',))
            if not cur.fetchone():
                password_hash = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode('utf-8')
                
                cur.execute("""
                    INSERT INTO security.users (email, password_hash, email_confirmed, is_active)
                    VALUES (%s, %s, 1, 2)
                """, ('admin@cnpj.com', password_hash))
                
                print("✅ Usuário admin criado: admin@cnpj.com / admin123")
            else:
                print("ℹ️ Usuário admin já existe")
            
            conn.commit()
            cur.close()
            conn.close()
            return True
            
        except psycopg2.OperationalError as e:
            attempt += 1
            print(f"⏳ Tentativa {attempt}/{max_attempts} - Banco não está pronto: {e}")
            if attempt < max_attempts:
                time.sleep(5)
            else:
                print(f"❌ Não foi possível conectar ao banco após {max_attempts} tentativas")
                return False
        except Exception as e:
            print(f"❌ Erro ao criar usuário admin: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return False

if __name__ == "__main__":
    if create_admin_user():
        sys.exit(0)
    else:
        sys.exit(1)
ADMINSCRIPT

RUN chmod +x /app/init_admin.py

EXPOSE 8430 8501

CMD ["bash"]