# 🏢 CNPJ API PRIVATE

API privada para **consultas completas de CNPJ**, com autenticação JWT, limites de uso por plano, filtros avançados e cruzamento inteligente de dados empresariais.

---

## 🚀 Instalação

### Opção 1: Com Docker (Recomendado)

#### Requisitos do Sistema

- **Docker** e **Docker Compose** instalados
- **50GB de espaço em disco** (para dados completos da Receita Federal)
- **8GB+ de RAM** recomendado (mínimo 4GB)
- **Conexão estável com internet** (download de ~5GB de dados)

#### ⚙️ Configuração de Memória (IMPORTANTE!)

Antes de iniciar, ajuste as configurações de memória no arquivo `database/scripts/import_cnpj_postgresql.py` de acordo com sua máquina:

```python
# Configurações de memória - AJUSTE CONFORME SUA MÁQUINA
MAX_RAM_GB = 30      # Limite de RAM (use 70% da RAM disponível)
MAX_SWAP_GB = 5      # Limite de SWAP
CHUNK_SIZE = 100_000 # Tamanho do chunk (reduza se tiver pouca memória)
N_WORKERS = 4        # Workers paralelos (número de cores da CPU)
DASK_THREADS = 4     # Threads dask (igual a N_WORKERS)
```

**Recomendações por configuração:**

| RAM do Sistema | MAX_RAM_GB | CHUNK_SIZE | N_WORKERS |
|---------------|------------|------------|-----------|
| 4GB           | 2          | 50_000     | 2         |
| 8GB           | 5          | 75_000     | 2         |
| 16GB          | 11         | 100_000    | 4         |
| 32GB          | 22         | 150_000    | 6         |
| 64GB+         | 45         | 200_000    | 8         |

#### Setup Rápido (Teste)

Para testar rapidamente a API sem baixar todos os dados da Receita:

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/cnpj-api-private.git
cd cnpj-api-private

# Setup rápido com dados de teste
make quick-start
```

Este comando irá:
- ✅ Configurar o banco PostgreSQL
- ✅ Criar usuário admin (admin@cnpj.com / admin123)
- ✅ Iniciar API em http://localhost:8430/docs
- ✅ Iniciar Dashboard Admin em http://localhost:8501
- ✅ Iniciar Interface de Consultas em http://localhost:8502

#### Setup Completo (Produção)

Para ambiente de produção com todos os dados da Receita Federal:

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/cnpj-api-private.git
cd cnpj-api-private

# IMPORTANTE: Ajuste as configurações de memória antes!
# Edite: database/scripts/import_cnpj_postgresql.py

# Setup completo com download da Receita Federal
make full-setup
```

⚠️ **ATENÇÃO**: Este processo pode demorar **4-6 horas** e irá:
- 📥 Baixar ~5GB de dados da Receita Federal
- 💾 Importar para PostgreSQL (ocupará ~50GB)
- 🔄 Criar índices e otimizações
- ✅ Configurar API e Dashboards

#### Comandos Docker Úteis

```bash
# Ver todos os comandos disponíveis
make help

# Iniciar serviços
make up

# Parar serviços
make down

# Ver logs
make logs
make logs-api    # Apenas API
make logs-db     # Apenas banco

# Acessar shell do container
make shell      # Shell da API
make db-shell   # Shell do PostgreSQL

# Fazer backup do banco
make backup

# Restaurar backup
make restore FILE=backups/arquivo.sql

# Ver estatísticas do banco
make stats

# Reset completo (CUIDADO: apaga todos os dados!)
make reset
```

---

### Opção 2: Instalação Manual (Sem Docker)

#### Requisitos

- **Python 3.11+**
- **PostgreSQL 15+**
- **50GB de espaço em disco**
- **8GB+ de RAM**

#### Passo a Passo

1. **Clone o repositório:**
```bash
git clone https://github.com/seu-usuario/cnpj-api-private.git
cd cnpj-api-private
```

2. **Configure o PostgreSQL:**
```bash
# Crie o banco de dados
sudo -u postgres psql
CREATE DATABASE cnpj_rede;
CREATE USER admin WITH PASSWORD 'admin123';
GRANT ALL PRIVILEGES ON DATABASE cnpj_rede TO admin;
\q

# Execute o script de inicialização
psql -U admin -d cnpj_rede -f init.sql
```

3. **Instale as dependências Python:**
```bash
# Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt
```

4. **Configure variáveis de ambiente:**
```bash
# Crie arquivo .env
cat > .env << EOF
DB_USER=admin
DB_PASSWORD=admin123
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cnpj_rede
SECRET_KEY=sua_chave_secreta_super_segura_aqui_32_chars_min
EOF
```

5. **Ajuste configurações de memória:**

Edite `database/scripts/import_cnpj_postgresql.py` conforme tabela de recomendações acima.

6. **Baixe e importe dados da Receita Federal:**
```bash
# Baixar dados (demora ~1 hora)
cd database/scripts
python dados_cnpj_baixa.py

# Importar para PostgreSQL (demora 3-5 horas)
python import_cnpj_postgresql.py
```

7. **Crie usuário admin:**
```bash
cd ../..
python -c "
import psycopg2
import bcrypt

conn = psycopg2.connect(
    host='localhost',
    database='cnpj_rede',
    user='admin',
    password='admin123'
)
cur = conn.cursor()

# Cria schema e tabela
cur.execute('CREATE SCHEMA IF NOT EXISTS security')
cur.execute('''
    CREATE TABLE IF NOT EXISTS security.users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email_confirmed INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 2,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# Cria usuário admin
password_hash = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode('utf-8')
cur.execute('''
    INSERT INTO security.users (email, password_hash, email_confirmed, is_active)
    VALUES (%s, %s, 1, 2)
''', ('admin@cnpj.com', password_hash))

conn.commit()
print('✅ Usuário admin criado!')
"
```

8. **Inicie os serviços:**
```bash
# Terminal 1 - API
uvicorn app.main:app --host 0.0.0.0 --port 8430 --reload

# Terminal 2 - Dashboard Admin
streamlit run app/streamlit_app.py --server.port 8501

# Terminal 3 - Interface de Consultas
streamlit run app/streamlit_front.py --server.port 8502
```

---

## 🖥️ Interfaces do Sistema

### 1. API REST (http://localhost:8430)
- **Documentação interativa:** http://localhost:8430/docs
- **Endpoints RESTful** para integração com sistemas
- **Autenticação JWT** para segurança

### 2. Dashboard Administrativo (http://localhost:8501)
- **Gerenciamento de usuários** e permissões
- **Estatísticas de uso** do sistema
- **Monitoramento** de requisições
- **Login:** admin@cnpj.com / admin123

### 3. Interface de Consultas (http://localhost:8502)
- **Interface visual** para testes e consultas
- **Exportação para Excel** dos resultados
- **Todos os endpoints** disponíveis visualmente
- **Login:** Use suas credenciais de usuário

![Interface de Consultas](docs/interface-consultas.png)

---

## 👤 Acesso ao Sistema

### Usuário Admin Padrão

Após o setup, um usuário administrador é criado automaticamente:
- **Email:** admin@cnpj.com
- **Senha:** admin123

⚠️ **IMPORTANTE:** Mude a senha padrão após o primeiro acesso!

### Criar Novo Usuário

```bash
curl -X POST "http://localhost:8430/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"seu@email.com","password":"suaSenhaForte123"}'
```

---

## 🔐 Autenticação (Login)

### Via API (para integrações)

```bash
curl -X POST "http://localhost:8430/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"seu@email.com","password":"suaSenhaForte123"}'
```

Resposta:
```json
{
  "access_token": "SEU_TOKEN_JWT_AQUI",
  "token_type": "bearer"
}
```

### Via Interface Web

1. Acesse http://localhost:8502
2. Digite email e senha
3. Clique em "Entrar"
4. Use a interface visual para consultas

---

## 🚦 Limites de Uso

| Tipo de Conta | Limite | is_active | Descrição |
|--------------|--------|-----------|-----------|
| **Gratuita** | 10 requisições/dia | 0 | Consultas básicas |
| **Limitada** | 3.000 requisições/mês | 1 | + Cruzamentos |
| **Ilimitada** | Sem restrições | 2 | Acesso total |

> ⚠️ Rotas de cruzamento exigem conta ativa (`is_active >= 1`)

---

## 📚 Endpoints da API

### Documentação Interativa

- **Swagger UI:** http://localhost:8430/docs
- **ReDoc:** http://localhost:8430/redoc

### Consultas Básicas

```bash
# 1. Buscar CNPJ específico
curl -X GET "http://localhost:8430/api/cnpj/60409075000152" \
  -H "Authorization: Bearer SEU_TOKEN"

# 2. Listar por UF
curl -X GET "http://localhost:8430/api/cnpj/uf/SP?page=1" \
  -H "Authorization: Bearer SEU_TOKEN"

# 3. Listar por município
curl -X GET "http://localhost:8430/api/cnpj/municipio/SAO%20PAULO?page=1" \
  -H "Authorization: Bearer SEU_TOKEN"

# 4. Listar por CNAE principal
curl -X GET "http://localhost:8430/api/cnpj/cnae_principal/1099699?page=1" \
  -H "Authorization: Bearer SEU_TOKEN"
```

### Consultas Combinadas

```bash
# 5. UF + CNAE principal
curl -X GET "http://localhost:8430/api/cnpj/uf/SP/cnae_principal/1099699?page=1" \
  -H "Authorization: Bearer SEU_TOKEN"

# 6. Município + CNAE
curl -X GET "http://localhost:8430/api/cnpj/municipio/SAO%20PAULO/cnae_principal/1099699?page=1" \
  -H "Authorization: Bearer SEU_TOKEN"
```

### 🔗 Cruzamentos e Relacionamentos (Conta Ativa)

```bash
# 7. CNPJs com mesmo endereço
curl -X GET "http://localhost:8430/api/cruzamentos/enderecos/compartilhados?endereco=RUA%20X" \
  -H "Authorization: Bearer SEU_TOKEN"

# 8. CNPJs com mesmo email
curl -X GET "http://localhost:8430/api/cruzamentos/emails/compartilhados?email=exemplo@mail.com" \
  -H "Authorization: Bearer SEU_TOKEN"

# 9. CNPJs com mesmo telefone
curl -X GET "http://localhost:8430/api/cruzamentos/telefones/compartilhados?ddd=11&telefone=12345678" \
  -H "Authorization: Bearer SEU_TOKEN"

# 10. Rede de relacionamentos
curl -X GET "http://localhost:8430/api/cruzamentos/rede/60409075000152" \
  -H "Authorization: Bearer SEU_TOKEN"

# 11. Análise de grupo econômico
curl -X GET "http://localhost:8430/api/cruzamentos/analise/grupo_economico/60409075000152" \
  -H "Authorization: Bearer SEU_TOKEN"
```

---

## 🛡️ Segurança

- **JWT:** Todas as rotas exigem autenticação
- **Bcrypt:** Senhas criptografadas
- **Rate Limiting:** Controle por usuário
- **Audit Log:** Registro de todas as operações
- **Auto-block:** Bloqueio por uso abusivo

---

## 📊 Estrutura do Banco de Dados

```
cnpj_rede (PostgreSQL)
├── cnpj.*              # Dados principais das empresas
│   ├── empresas        # Informações cadastrais
│   ├── socios          # Quadro societário
│   └── simples         # Dados do Simples Nacional
├── rede.*              # Relacionamentos e vínculos
│   ├── enderecos       # Endereços únicos
│   ├── emails          # Emails únicos
│   └── telefones       # Telefones únicos
├── links.*             # Cruzamentos de dados
│   ├── cnpj_endereco   # Vínculos CNPJ-endereço
│   ├── cnpj_email      # Vínculos CNPJ-email
│   └── cnpj_telefone   # Vínculos CNPJ-telefone
└── security.*          # Usuários e autenticação
    └── users           # Tabela de usuários
```

---

## 🔧 Desenvolvimento

### Estrutura do Projeto

```
cnpj-api-private/
├── app/                    # Código da aplicação
│   ├── api/               # Endpoints da API
│   ├── auth/              # Autenticação JWT
│   ├── models/            # Modelos do banco
│   ├── streamlit_app.py   # Dashboard admin
│   └── streamlit_front.py # Interface de consultas
├── database/              
│   └── scripts/           # Scripts de importação
├── docker-compose.yml     # Configuração Docker
├── Dockerfile            # Build das imagens
├── Makefile              # Comandos úteis
├── requirements.txt      # Dependências Python
└── init.sql             # Schema do banco
```

### Variáveis de Ambiente

```env
# Banco de Dados
DB_USER=admin
DB_PASSWORD=admin123
DB_HOST=localhost  # ou 'db' para Docker
DB_PORT=5432
DB_NAME=cnpj_rede

# JWT
SECRET_KEY=sua_chave_secreta_super_segura_aqui_32_chars_min

# Configurações de Importação
MAX_RAM_GB=30        # Ajuste conforme sua máquina
MAX_SWAP_GB=5
CHUNK_SIZE=100000
N_WORKERS=4
DASK_THREADS=4

# Docker Only
SKIP_DOWNLOAD=false  # Pula download se true
SKIP_IMPORT=false    # Pula importação se true
DEBUG_MODE=false     # Mantém container rodando se true
```

### 🐛 Troubleshooting

**Erro de memória durante importação:**
- Reduza `MAX_RAM_GB` e `CHUNK_SIZE` no arquivo de configuração
- Aumente o swap do sistema se possível

**Processo muito lento:**
- Aumente `N_WORKERS` se tiver cores de CPU disponíveis
- Use SSD ao invés de HDD para melhor performance

**Container não inicia:**
```bash
# Verificar logs
docker compose logs -f importer

# Entrar no container para debug
docker compose run --rm importer bash
```

**PostgreSQL connection refused:**
```bash
# Verificar se PostgreSQL está rodando
sudo systemctl status postgresql

# Verificar configurações em pg_hba.conf
sudo nano /etc/postgresql/15/main/pg_hba.conf
# Adicione: host all all 127.0.0.1/32 md5
```

### Contribuindo

1. Fork o projeto
2. Crie sua feature branch (`git checkout -b feature/NovaFuncionalidade`)
3. Commit suas mudanças (`git commit -m 'Add: Nova funcionalidade'`)
4. Push para a branch (`git push origin feature/NovaFuncionalidade`)
5. Abra um Pull Request

---

## 📝 Licença

Projeto privado. Todos os direitos reservados.

---

## 📞 Suporte

- **Issues:** [Abra uma issue no GitHub](https://github.com/tiagorahal/cnpj-api-private/issues)
- **Email:** rahal.aires@gmail.com
- **API Docs:** http://localhost:8430/docs
- **Dashboard Admin:** http://localhost:8501
- **Interface Consultas:** http://localhost:8502

---
