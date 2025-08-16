"""
Script unificado para importar base CNPJ para PostgreSQL
Combina os 3 scripts originais em um único processo
"""
import os

if os.getenv("NON_INTERACTIVE") == "true":
    def input(*args, **kwargs):
        return "y"
    
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
import glob, time, os, sys, zipfile
import dask.dataframe as dd
import dask
import gc
import psutil
import re, string, unicodedata
import numpy as np
from datetime import datetime

# ============ CONFIGURAÇÕES ============
# Configurações de conexão PostgreSQL
PG_HOST = 'localhost'
PG_PORT = 5432
PG_DATABASE = 'cnpj_rede'
PG_USER = 'admin'
PG_PASSWORD = 'admin123'

# Configurações de memória
MAX_RAM_GB = 30      # Limite de RAM
MAX_SWAP_GB = 5      # Limite de SWAP
CHUNK_SIZE = 100_000 # Tamanho do chunk
N_WORKERS = 4        # Workers paralelos
DASK_THREADS = 4     # Threads dask

# Configurações de caminhos
pasta_compactados = r"../dados-publicos-zip"
pasta_saida = r"../dados-publicos"
bApagaDescompactadosAposUso = True

# String de conexão PostgreSQL
PG_CONNECTION_STRING = f'postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}'

# ============ FUNÇÕES AUXILIARES ============

def ram_ok():
    """Verifica se RAM/SWAP está abaixo do limite"""
    v = psutil.virtual_memory()
    s = psutil.swap_memory()
    ram_gb = v.used / 1024 / 1024 / 1024
    swap_gb = s.used / 1024 / 1024 / 1024
    return (ram_gb < MAX_RAM_GB) and (swap_gb < MAX_SWAP_GB)

def wait_for_ram():
    while not ram_ok():
        print("Memória/swap alta, aguardando liberar recursos...")
        time.sleep(30)

def criar_engine_postgresql():
    """Cria engine PostgreSQL com configurações otimizadas"""
    engine = create_engine(
        PG_CONNECTION_STRING,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={
            "options": "-c statement_timeout=0 -c lock_timeout=0"
        }
    )
    return engine

def executar_sql(engine, sql_commands):
    """Executa comandos SQL com tratamento de erro"""
    with engine.begin() as conn:
        for sql in sql_commands.split(';'):
            sql = sql.strip()
            if sql:
                print(f"Executando: {sql[:100]}...")
                try:
                    conn.execute(text(sql))
                except Exception as e:
                    print(f"Erro ao executar SQL: {e}")
                    raise

# ============ PARTE 1: IMPORTAÇÃO DA BASE CNPJ ============

def descompactar_arquivos():
    """Descompacta arquivos ZIP"""
    arquivos_zip = list(glob.glob(os.path.join(pasta_compactados, r'*.zip')))
    
    if len(arquivos_zip) != 37:
        print(f'AVISO: A pasta {pasta_compactados} tem {len(arquivos_zip)} arquivos (esperado: 37)')
        resp = input('Prosseguir assim mesmo? (y/n) ')
        if resp.lower() != 'y':
            sys.exit()
    
    print('Descompactando arquivos...')
    for arq in arquivos_zip:
        print(f'  {os.path.basename(arq)}')
        with zipfile.ZipFile(arq, 'r') as zip_ref:
            zip_ref.extractall(pasta_saida)

def criar_schemas(engine):
    """Cria schemas no PostgreSQL"""
    sql = """
    CREATE SCHEMA IF NOT EXISTS cnpj;
    CREATE SCHEMA IF NOT EXISTS rede;
    CREATE SCHEMA IF NOT EXISTS links;
    """
    executar_sql(engine, sql)

def carregar_tabela_codigo(engine, extensao, nome_tabela):
    """Carrega tabelas de código (CNAE, MOTIVO, etc)"""
    arquivo = list(glob.glob(os.path.join(pasta_saida, '*' + extensao)))[0]
    print(f'Carregando {arquivo} na tabela cnpj.{nome_tabela}')
    
    dtab = pd.read_csv(arquivo, dtype=str, sep=';', encoding='latin1', 
                       header=None, names=['codigo', 'descricao'])
    
    dtab.to_sql(nome_tabela, engine, schema='cnpj', 
                if_exists='replace', index=False, method='multi')
    
    # Criar índice
    sql = f"CREATE INDEX IF NOT EXISTS idx_{nome_tabela}_codigo ON cnpj.{nome_tabela}(codigo);"
    executar_sql(engine, sql)
    
    if bApagaDescompactadosAposUso:
        os.remove(arquivo)
    gc.collect()

def criar_tabelas_principais(engine):
    """Cria tabelas principais no PostgreSQL"""
    sql = """
    -- Tabela empresas
    CREATE TABLE IF NOT EXISTS cnpj.empresas (
        cnpj_basico TEXT,
        razao_social TEXT,
        natureza_juridica TEXT,
        qualificacao_responsavel TEXT,
        capital_social NUMERIC,
        porte_empresa TEXT,
        ente_federativo_responsavel TEXT
    );
    
    -- Tabela estabelecimento
    CREATE TABLE IF NOT EXISTS cnpj.estabelecimento (
        cnpj_basico TEXT,
        cnpj_ordem TEXT,
        cnpj_dv TEXT,
        cnpj TEXT,
        matriz_filial TEXT,
        nome_fantasia TEXT,
        situacao_cadastral TEXT,
        data_situacao_cadastral TEXT,
        motivo_situacao_cadastral TEXT,
        nome_cidade_exterior TEXT,
        pais TEXT,
        data_inicio_atividades TEXT,
        cnae_fiscal TEXT,
        cnae_fiscal_secundaria TEXT,
        tipo_logradouro TEXT,
        logradouro TEXT,
        numero TEXT,
        complemento TEXT,
        bairro TEXT,
        cep TEXT,
        uf TEXT,
        municipio TEXT,
        ddd1 TEXT,
        telefone1 TEXT,
        ddd2 TEXT,
        telefone2 TEXT,
        ddd_fax TEXT,
        fax TEXT,
        correio_eletronico TEXT,
        situacao_especial TEXT,
        data_situacao_especial TEXT
    );
    
    -- Tabela socios
    CREATE TABLE IF NOT EXISTS cnpj.socios (
        cnpj_basico TEXT,
        cnpj TEXT,
        identificador_de_socio TEXT,
        nome_socio TEXT,
        cnpj_cpf_socio TEXT,
        qualificacao_socio TEXT,
        data_entrada_sociedade TEXT,
        pais TEXT,
        representante_legal TEXT,
        nome_representante TEXT,
        qualificacao_representante_legal TEXT,
        faixa_etaria TEXT
    );
    
    -- Tabela simples
    CREATE TABLE IF NOT EXISTS cnpj.simples (
        cnpj_basico TEXT,
        opcao_simples TEXT,
        data_opcao_simples TEXT,
        data_exclusao_simples TEXT,
        opcao_mei TEXT,
        data_opcao_mei TEXT,
        data_exclusao_mei TEXT
    );
    
    -- Tabela referencia
    CREATE TABLE IF NOT EXISTS cnpj.referencia (
        referencia TEXT,
        valor TEXT
    );
    """
    executar_sql(engine, sql)

def carregar_arquivo_tipo(engine, nome_tabela, tipo, colunas):
    """Carrega arquivos por tipo (EMPRESAS, ESTABELECIMENTOS, etc)"""
    arquivos = list(glob.glob(os.path.join(pasta_saida, '*' + tipo)))
    
    for arq in arquivos:
        wait_for_ram()
        print(f'Carregando {os.path.basename(arq)} em cnpj.{nome_tabela}')
        
        try:
            # Ler com Dask
            ddf = dd.read_csv(arq, sep=';', header=None, names=colunas, 
                            encoding='latin1', dtype=str, na_filter=None,
                            blocksize=CHUNK_SIZE * 200)
            df = ddf.compute(scheduler="threads", num_workers=N_WORKERS)
        except Exception as e:
            print(f"Erro com Dask, usando pandas: {e}")
            df = pd.read_csv(arq, sep=';', header=None, names=colunas, 
                           encoding='latin1', dtype=str)
        
        # Ajustes específicos
        if nome_tabela == 'empresas' and 'capital_social_str' in colunas:
            df['capital_social'] = df['capital_social_str'].str.replace(',', '.').astype(float)
            df = df.drop('capital_social_str', axis=1)
        
        if nome_tabela == 'estabelecimento':
            df['cnpj'] = df['cnpj_basico'] + df['cnpj_ordem'] + df['cnpj_dv']
        
        # Carregar no PostgreSQL
        df.to_sql(nome_tabela, engine, schema='cnpj', 
                 if_exists='append', index=False, method='multi',
                 chunksize=10000)
        
        if bApagaDescompactadosAposUso:
            os.remove(arq)
        
        gc.collect()
        wait_for_ram()

def criar_indices_principais(engine):
    """Cria índices nas tabelas principais"""
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_empresas_cnpj_basico ON cnpj.empresas(cnpj_basico);",
        "CREATE INDEX IF NOT EXISTS idx_empresas_razao_social ON cnpj.empresas(razao_social);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimento_cnpj_basico ON cnpj.estabelecimento(cnpj_basico);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimento_cnpj ON cnpj.estabelecimento(cnpj);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimento_nome_fantasia ON cnpj.estabelecimento(nome_fantasia);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimento_matriz_filial ON cnpj.estabelecimento(matriz_filial);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimento_situacao ON cnpj.estabelecimento(situacao_cadastral);",
        "CREATE INDEX IF NOT EXISTS idx_socios_cnpj_basico ON cnpj.socios(cnpj_basico);",
        "CREATE INDEX IF NOT EXISTS idx_socios_cnpj ON cnpj.socios(cnpj);",
        "CREATE INDEX IF NOT EXISTS idx_socios_cnpj_cpf_socio ON cnpj.socios(cnpj_cpf_socio);",
        "CREATE INDEX IF NOT EXISTS idx_socios_nome_socio ON cnpj.socios(nome_socio);",
        "CREATE INDEX IF NOT EXISTS idx_simples_cnpj_basico ON cnpj.simples(cnpj_basico);"
    ]
    
    for idx in indices:
        print(f"Criando índice: {idx[:50]}...")
        executar_sql(engine, idx)

# ============ PARTE 2: NORMALIZAÇÃO E LINKS (ETE) ============

dicAbreviaturas = {
    "A":"AREA", "AC":"ACESSO", "ACA":"ACAMPAMENTO", "AD":"ADRO",
    "AE":"AREA ESPECIAL", "AER":"AEROPORTO", "AL":"ALAMEDA", "AR":"AREA",
    "ART":"ARTERIA", "AT":"ALTO", "ATL":"ATALHO", "AV":"AVENIDA",
    "AVEN":"AVENIDA", "AVC":"AVENIDA CONTORNO", "BAL":"BALNEARIO", "BC":"BECO",
    "BEL":"BELVEDERE", "BL":"BLOCO", "BSQ":"BOSQUE", "BVD":"BOULEVARD",
    "BX":"BAIXA", "CAL":"CALCADA", "CAM":"CAMINHO", "CAN":"CANAL",
    "CH":"CHACARA", "CHA":"CHAPADAO", "CIR":"CIRCULAR", "CJ":"CONJUNTO",
    "CMP":"COMPLEXO VIARIO", "CND":"CONDOMINIO", "COL":"COLONIA",
    "CON":"CONDOMINIO", "COR":"CORREDOR", "CPO":"CAMPO", "CRG":"CORREGO",
    "DSC":"DESCIDA", "DSV":"DESVIO", "DT":"DISTRITO", "ENT":"ENTRADA PARTICULAR",
    "EQ":"ENTREQUADRA", "ESC":"ESCADA", "ESP":"ESPLANADA", "EST":"ESTRADA",
    "ETC":"ESTACAO", "ETD":"ESTADIO", "ETN":"ESTANCIA", "EVD":"ELEVADA",
    "FAV":"FAVELA", "FAZ":"FAZENDA", "FER":"FERROVIA", "FNT":"FONTE",
    "FRA":"FEIRA", "FTE":"FORTE", "GJA":"GRANJA", "HAB":"HABITACIONAL",
    "IA":"ILHA", "JD":"JARDIM", "LAD":"LADEIRA", "LD":"LADEIRA",
    "LG":"LAGO", "LGA":"LAGO", "LGO":"LARGO", "LOT":"LOTEAMENTO",
    "LRG":"LARGO", "MNA":"MARINA", "MOD":"MODULO", "MRO":"MORRO",
    "MTE":"MONTE", "NUC":"NUCLEO", "OTR":"OUTROS", "PAR":"PARALELA",
    "PAS":"PASSARELA", "PAT":"PATIO", "PC":"PRACA", "PCA":"PRACA",
    "PDA":"PARADA", "PDO":"PARADOURO", "PNT":"PONTA", "PQ":"PARQUE",
    "PR":"PRAIA", "PRL":"PROLONGAMENTO", "PRQ":"PARQUE", "PSA":"PASSARELA",
    "PSG":"PASSAGEM", "PTE":"PONTE", "PTO":"PATIO", "Q":"QUADRA",
    "QD":"QUADRA", "QTA":"QUINTAS", "R":"RUA", "RAM":"RAMAL",
    "RDV":"RODOVIA", "REC":"RECANTO", "RER":"RETIRO", "RES":"RESIDENCIAL",
    "RET":"RETA", "RMP":"RAMPA", "ROD":"RODOVIA", "ROT":"ROTULA",
    "RTN":"RETORNO", "RTT":"ROTATORIA", "SIT":"SITIO", "SRV":"SERVIDAO",
    "ST":"SETOR", "SUB":"SUBIDA", "TCH":"TRINCHEIRA", "TER":"TERMINAL",
    "TR":"TRAVESSA", "TRV":"TREVO", "TV":"TRAVESSA", "UNI":"UNIDADE",
    "V":"VIA", "VAL":"VALE", "VD":"VIADUTO", "VER":"VEREDA",
    "VEV":"VIELA", "VEX":"VIAEXPRESSA", "VIA":"VIA", "VL":"VILA",
    "VLA":"VIELA", "VLE":"VALE", "VRT":"VARIANTE"
}

def soCaracteres(data):
    if data is None:
        return ''
    t = ''.join(x for x in unicodedata.normalize('NFKD', data) if x in string.printable)
    return re.sub(r'\W', ' ', t)

def normalizaEndereco(enderecoIn, ignoraEnderecoSoComNumeros=True, ignoraEnderecoSemNumeros=True):
    if not enderecoIn:
        return ''
    
    enderecoAux = re.sub(r'([0-9]+)[.]([0-9]+)', '\\1\\2', enderecoIn).upper()
    enderecoAux = re.sub(r'([A-Z])(\d)', '\\1 \\2', enderecoAux)
    enderecoAux = re.sub(r'(\d)([A-Z])', '\\1 \\2', enderecoAux)
    
    enderecoAux = " %s " % (soCaracteres(enderecoAux))
    enderecoAux = enderecoAux.replace(' S N ', ' ')
    lendereco = enderecoAux.split()
    
    if len(lendereco) == 0:
        return ''
    
    if lendereco[0] == 'LOC':
        lendereco[0] = ''
    
    palavras = set()
    numeros = []
    
    for k, pedaco in enumerate(lendereco):
        pedacoAjustado = pedaco
        if pedaco in dicAbreviaturas:
            if len(pedaco) > 1 or k <= 1:
                pedacoAjustado = dicAbreviaturas[pedaco]
        
        if pedacoAjustado:
            if pedacoAjustado.isdigit():
                pedacoAjustado = pedacoAjustado.lstrip('0')
                if pedacoAjustado:
                    numeros.append(pedacoAjustado)
            else:
                palavras.add(pedacoAjustado)
    
    palavrasOrdenadas = sorted(list(palavras))
    
    if ignoraEnderecoSemNumeros and not numeros:
        return ''
    
    if ignoraEnderecoSoComNumeros and not palavrasOrdenadas:
        return ''
    
    palavrasOrdenadas.extend(numeros)
    endereco = ' '.join(palavrasOrdenadas)
    return endereco

def ajustaTelefone(telefoneIn):
    if not telefoneIn or telefoneIn == '0 0':
        return ''
    
    telefoneIn = ' '.join(telefoneIn.split()).strip()
    
    if telefoneIn[-7:] in ('0000000', '1111111', '2222222', '3333333', '4444444',
                           '5555555', '6666666', '7777777', '8888888', '9999999'):
        return ''
    
    if ' ' in telefoneIn:
        pos = telefoneIn.find(' ')
        ddd, t = telefoneIn[:pos], re.sub(' ', '', telefoneIn[pos:])
        if len(ddd) > 2:
            ddd = ddd[-2:]
        if len(t) < 4:
            return ''
        return ddd + ' ' + t
    elif len(telefoneIn) < 9:
        return ''
    else:
        return telefoneIn

def ajusta_email(emailin):
    if not emailin:
        return ''
    
    emailin = str(emailin).strip()
    if emailin.startswith("'"):
        emailin = emailin[1:]
    if emailin.endswith("'"):
        emailin = emailin[:-1]
    
    if '@' not in emailin:
        return ''
    
    return emailin.lower()

def processar_enderecos(engine):
    """Processa e normaliza endereços"""
    print("Processando endereços...")
    
    # Criar tabela temporária
    sql = """
    CREATE TABLE IF NOT EXISTS links.endereco_temp (
        cnpj TEXT,
        endereco TEXT,
        situacao TEXT
    );
    """
    executar_sql(engine, sql)
    
    # Processar em lotes
    query = """
    SELECT cnpj, situacao_cadastral as situacao,
           CONCAT(logradouro, ' ', numero, ' ', complemento) as logradouro_completo,
           COALESCE(m.descricao, nome_cidade_exterior) as municipio,
           CASE WHEN uf != 'EX' THEN uf ELSE p.descricao END as uf
    FROM cnpj.estabelecimento e
    LEFT JOIN cnpj.municipio m ON m.codigo = e.municipio
    LEFT JOIN cnpj.pais p ON p.codigo = e.pais
    LIMIT %s OFFSET %s
    """
    
    offset = 0
    batch_size = 100000
    
    while True:
        wait_for_ram()
        df = pd.read_sql(query, engine, params=(batch_size, offset))
        
        if df.empty:
            break
        
        # Normalizar endereços
        df['endereco_norm'] = df['logradouro_completo'].apply(normalizaEndereco)
        df['endereco'] = df['endereco_norm'] + '-' + df['municipio'] + '-' + df['uf']
        
        # Filtrar endereços válidos
        df = df[df['endereco_norm'] != '']
        
        if not df.empty:
            df[['cnpj', 'endereco', 'situacao']].to_sql(
                'endereco_temp', engine, schema='links',
                if_exists='append', index=False, method='multi'
            )
        
        offset += batch_size
        gc.collect()
        print(f"  Processados {offset} registros...")

def processar_telefones(engine):
    """Processa e normaliza telefones"""
    print("Processando telefones...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS links.telefone_temp (
        cnpj TEXT,
        telefone TEXT,
        situacao TEXT
    );
    """
    executar_sql(engine, sql)
    
    query = """
    SELECT cnpj, situacao_cadastral as situacao,
           ddd1, telefone1, ddd2, telefone2, ddd_fax, fax
    FROM cnpj.estabelecimento
    LIMIT %s OFFSET %s
    """
    
    offset = 0
    batch_size = 100000
    
    while True:
        wait_for_ram()
        df = pd.read_sql(query, engine, params=(batch_size, offset))
        
        if df.empty:
            break
        
        telefones = []
        for _, row in df.iterrows():
            cnpj = row['cnpj']
            situacao = row['situacao']
            
            t1 = ajustaTelefone(f"{row['ddd1']} {row['telefone1']}")
            t2 = ajustaTelefone(f"{row['ddd2']} {row['telefone2']}")
            t3 = ajustaTelefone(f"{row['ddd_fax']} {row['fax']}")
            
            for tel in set([t1, t2, t3]):
                if tel:
                    telefones.append([cnpj, tel, situacao])
        
        if telefones:
            df_tel = pd.DataFrame(telefones, columns=['cnpj', 'telefone', 'situacao'])
            df_tel.to_sql('telefone_temp', engine, schema='links',
                         if_exists='append', index=False, method='multi')
        
        offset += batch_size
        gc.collect()
        print(f"  Processados {offset} registros...")

def processar_emails(engine):
    """Processa e normaliza emails"""
    print("Processando emails...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS links.email_temp (
        cnpj TEXT,
        email TEXT,
        situacao TEXT
    );
    """
    executar_sql(engine, sql)
    
    query = """
    SELECT cnpj, situacao_cadastral as situacao, correio_eletronico as email
    FROM cnpj.estabelecimento
    WHERE correio_eletronico IS NOT NULL AND correio_eletronico != ''
    LIMIT %s OFFSET %s
    """
    
    offset = 0
    batch_size = 100000
    
    while True:
        wait_for_ram()
        df = pd.read_sql(query, engine, params=(batch_size, offset))
        
        if df.empty:
            break
        
        df['email'] = df['email'].apply(ajusta_email)
        df = df[df['email'] != '']
        
        if not df.empty:
            df[['cnpj', 'email', 'situacao']].to_sql(
                'email_temp', engine, schema='links',
                if_exists='append', index=False, method='multi'
            )
        
        offset += batch_size
        gc.collect()
        print(f"  Processados {offset} registros...")

def criar_links_ete(engine):
    """Cria tabela de links ETE"""
    print("Criando links ETE...")
    
    sql = """
    -- Links de endereço
    CREATE TABLE IF NOT EXISTS links.link_ete AS
    WITH endereco_count AS (
        SELECT endereco, COUNT(*) as contagem
        FROM links.endereco_temp
        WHERE situacao = '02'
        GROUP BY endereco
        HAVING COUNT(*) > 1
    )
    SELECT 
        'PJ_' || e.cnpj as id1,
        'EN_' || e.endereco as id2,
        'end' as descricao,
        ec.contagem as valor
    FROM links.endereco_temp e
    INNER JOIN endereco_count ec ON e.endereco = ec.endereco;
    
    -- Links de telefone
    INSERT INTO links.link_ete
    WITH telefone_count AS (
        SELECT telefone, COUNT(*) as contagem
        FROM links.telefone_temp
        WHERE situacao = '02'
        GROUP BY telefone
        HAVING COUNT(*) > 1
    )
    SELECT 
        'PJ_' || t.cnpj as id1,
        'TE_' || t.telefone as id2,
        'tel' as descricao,
        tc.contagem as valor
    FROM links.telefone_temp t
    INNER JOIN telefone_count tc ON t.telefone = tc.telefone;
    
    -- Links de email
    INSERT INTO links.link_ete
    WITH email_count AS (
        SELECT email, COUNT(*) as contagem
        FROM links.email_temp
        WHERE situacao = '02'
        GROUP BY email
        HAVING COUNT(*) > 1
    )
    SELECT 
        'PJ_' || e.cnpj as id1,
        'EM_' || e.email as id2,
        'email' as descricao,
        ec.contagem as valor
    FROM links.email_temp e
    INNER JOIN email_count ec ON e.email = ec.email;
    
    -- Criar índices
    CREATE INDEX IF NOT EXISTS idx_link_ete_id1 ON links.link_ete(id1);
    CREATE INDEX IF NOT EXISTS idx_link_ete_id2 ON links.link_ete(id2);
    
    -- Limpar tabelas temporárias
    DROP TABLE IF EXISTS links.endereco_temp;
    DROP TABLE IF EXISTS links.telefone_temp;
    DROP TABLE IF EXISTS links.email_temp;
    """
    executar_sql(engine, sql)

# ============ PARTE 3: CRIAÇÃO DA REDE DE LIGAÇÕES ============

def criar_tabela_ligacao(engine):
    """Cria tabela de ligação entre entidades"""
    print("Criando tabela de ligação...")
    
    sql = """
    -- Criar tabela de ligação
    CREATE TABLE IF NOT EXISTS rede.ligacao AS
    
    -- PJ->PJ vínculo sócio pessoa jurídica
    SELECT 
        'PJ_' || s.cnpj_cpf_socio as id1,
        'PJ_' || s.cnpj as id2,
        COALESCE(q.descricao, 'Sócio') as descricao,
        'socios' as comentario
    FROM cnpj.socios s
    LEFT JOIN cnpj.qualificacao_socio q ON q.codigo = s.qualificacao_socio
    WHERE LENGTH(s.cnpj_cpf_socio) = 14
    
    UNION ALL
    
    -- PF->PJ vínculo de sócio pessoa física
    SELECT 
        'PF_' || s.cnpj_cpf_socio || '-' || s.nome_socio as id1,
        'PJ_' || s.cnpj as id2,
        COALESCE(q.descricao, 'Sócio') as descricao,
        'socios' as comentario
    FROM cnpj.socios s
    LEFT JOIN cnpj.qualificacao_socio q ON q.codigo = s.qualificacao_socio
    WHERE LENGTH(s.cnpj_cpf_socio) = 11 AND s.nome_socio != ''
    
    UNION ALL
    
    -- PE->PJ empresa sócia no exterior
    SELECT 
        'PE_' || s.nome_socio as id1,
        'PJ_' || s.cnpj as id2,
        COALESCE(q.descricao, 'Sócio Exterior') as descricao,
        'socios' as comentario
    FROM cnpj.socios s
    LEFT JOIN cnpj.qualificacao_socio q ON q.codigo = s.qualificacao_socio
    WHERE LENGTH(s.cnpj_cpf_socio) != 14 
      AND LENGTH(s.cnpj_cpf_socio) != 11 
      AND s.cnpj_cpf_socio = ''
    
    UNION ALL
    
    -- PF->PE representante legal de empresa sócia no exterior
    SELECT 
        'PF_' || s.representante_legal || '-' || s.nome_representante as id1,
        'PE_' || s.nome_socio as id2,
        'rep-sócio-' || COALESCE(q.descricao, 'Representante') as descricao,
        'socios' as comentario
    FROM cnpj.socios s
    LEFT JOIN cnpj.qualificacao_socio q ON q.codigo = s.qualificacao_representante_legal
    WHERE LENGTH(s.cnpj_cpf_socio) != 14 
      AND LENGTH(s.cnpj_cpf_socio) != 11 
      AND s.cnpj_cpf_socio = ''
      AND s.representante_legal != '***000000**'
    
    UNION ALL
    
    -- PF->PJ representante legal PJ->PJ
    SELECT 
        'PF_' || s.representante_legal || '-' || s.nome_representante as id1,
        'PJ_' || s.cnpj_cpf_socio as id2,
        'rep-sócio-' || COALESCE(q.descricao, 'Representante') as descricao,
        'socios' as comentario
    FROM cnpj.socios s
    LEFT JOIN cnpj.qualificacao_socio q ON q.codigo = s.qualificacao_representante_legal
    WHERE LENGTH(s.cnpj_cpf_socio) = 14 
      AND s.representante_legal != '***000000**'
    
    UNION ALL
    
    -- PF->PF representante legal de sócio PF
    SELECT 
        'PF_' || s.representante_legal || '-' || s.nome_representante as id1,
        'PF_' || s.cnpj_cpf_socio || '-' || s.nome_socio as id2,
        'rep-sócio-' || COALESCE(q.descricao, 'Representante') as descricao,
        'socios' as comentario
    FROM cnpj.socios s
    LEFT JOIN cnpj.qualificacao_socio q ON q.codigo = s.qualificacao_representante_legal
    WHERE LENGTH(s.cnpj_cpf_socio) = 11 
      AND s.representante_legal != '***000000**'
    
    UNION ALL
    
    -- PJ filial-> PJ matriz
    SELECT 
        'PJ_' || f.cnpj as id1,
        'PJ_' || m.cnpj as id2,
        'filial' as descricao,
        'estabelecimento' as comentario
    FROM cnpj.estabelecimento f
    INNER JOIN cnpj.estabelecimento m 
        ON f.cnpj_basico = m.cnpj_basico 
        AND m.matriz_filial = '1'
    WHERE f.matriz_filial = '2';
    
    -- Criar índices
    CREATE INDEX IF NOT EXISTS idx_ligacao_id1 ON rede.ligacao(id1);
    CREATE INDEX IF NOT EXISTS idx_ligacao_id2 ON rede.ligacao(id2);
    """
    
    executar_sql(engine, sql)

def criar_tabela_busca(engine):
    """Cria tabela para busca textual"""
    print("Criando tabela de busca textual...")
    
    sql = """
    -- Criar extensão para busca textual (PostgreSQL)
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    
    -- Criar tabela de busca
    CREATE TABLE IF NOT EXISTS rede.id_search (
        id_descricao TEXT PRIMARY KEY
    );
    
    -- Inserir dados para busca
    INSERT INTO rede.id_search (id_descricao)
    SELECT DISTINCT id_descricao FROM (
        -- PJs com razão social
        SELECT 'PJ_' || e.cnpj || '-' || emp.razao_social as id_descricao
        FROM cnpj.estabelecimento e
        INNER JOIN cnpj.empresas emp ON e.cnpj_basico = emp.cnpj_basico
        WHERE e.matriz_filial = '1'
        
        UNION
        
        -- PJs com nome fantasia
        SELECT 'PJ_' || e.cnpj || '-' || e.nome_fantasia as id_descricao
        FROM cnpj.estabelecimento e
        WHERE e.nome_fantasia IS NOT NULL AND e.nome_fantasia != ''
        
        UNION
        
        -- Pessoas físicas e empresas do exterior
        SELECT id1 as id_descricao
        FROM rede.ligacao
        WHERE SUBSTRING(id1, 1, 3) != 'PJ_'
        
        UNION
        
        SELECT id2 as id_descricao
        FROM rede.ligacao
        WHERE SUBSTRING(id2, 1, 3) != 'PJ_'
        
        UNION
        
        -- Links ETE
        SELECT id1 as id_descricao
        FROM links.link_ete
        WHERE SUBSTRING(id1, 1, 3) != 'PJ_'
        
        UNION
        
        SELECT id2 as id_descricao
        FROM links.link_ete
        WHERE SUBSTRING(id2, 1, 3) != 'PJ_'
    ) t;
    
    -- Criar índice GIN para busca rápida
    CREATE INDEX IF NOT EXISTS idx_id_search_gin 
    ON rede.id_search USING gin(id_descricao gin_trgm_ops);
    """
    
    executar_sql(engine, sql)

def atualizar_tabela_socios(engine):
    """Atualiza tabela de sócios com CNPJ da matriz"""
    print("Atualizando tabela de sócios...")
    
    sql = """
    -- Adicionar CNPJ da matriz aos sócios
    UPDATE cnpj.socios s
    SET cnpj = e.cnpj
    FROM cnpj.estabelecimento e
    WHERE s.cnpj_basico = e.cnpj_basico
      AND e.matriz_filial = '1';
    
    -- Criar índices adicionais
    CREATE INDEX IF NOT EXISTS idx_socios_nome_socio ON cnpj.socios(nome_socio);
    CREATE INDEX IF NOT EXISTS idx_socios_representante ON cnpj.socios(representante_legal);
    CREATE INDEX IF NOT EXISTS idx_socios_nome_representante ON cnpj.socios(nome_representante);
    """
    
    executar_sql(engine, sql)

def criar_views_auxiliares(engine):
    """Cria views auxiliares para facilitar consultas"""
    print("Criando views auxiliares...")
    
    sql = """
    -- View de empresas ativas
    CREATE OR REPLACE VIEW cnpj.empresas_ativas AS
    SELECT e.*, est.cnpj, est.nome_fantasia, est.situacao_cadastral
    FROM cnpj.empresas e
    INNER JOIN cnpj.estabelecimento est ON e.cnpj_basico = est.cnpj_basico
    WHERE est.matriz_filial = '1' AND est.situacao_cadastral = '02';
    
    -- View de estatísticas
    CREATE OR REPLACE VIEW cnpj.estatisticas AS
    SELECT 
        (SELECT COUNT(*) FROM cnpj.empresas) as total_empresas,
        (SELECT COUNT(*) FROM cnpj.estabelecimento) as total_estabelecimentos,
        (SELECT COUNT(*) FROM cnpj.socios) as total_socios,
        (SELECT COUNT(*) FROM cnpj.estabelecimento WHERE situacao_cadastral = '02') as estabelecimentos_ativos,
        (SELECT COUNT(*) FROM rede.ligacao) as total_ligacoes,
        (SELECT COUNT(*) FROM links.link_ete) as total_links_ete;
    """
    
    executar_sql(engine, sql)

def adicionar_estatisticas(engine):
    """Adiciona estatísticas e informações de referência"""
    print("Adicionando estatísticas...")
    
    # Obter data de referência
    data_ref = datetime.now().strftime('%d/%m/%Y')
    
    # Obter contagens
    with engine.connect() as conn:
        qtde_cnpjs = conn.execute(text("SELECT COUNT(*) FROM cnpj.estabelecimento")).scalar()
        qtde_empresas = conn.execute(text("SELECT COUNT(*) FROM cnpj.empresas")).scalar()
        qtde_socios = conn.execute(text("SELECT COUNT(*) FROM cnpj.socios")).scalar()
    
    sql = f"""
    INSERT INTO cnpj.referencia (referencia, valor) VALUES
    ('data_atualizacao', '{data_ref}'),
    ('qtde_cnpjs', '{qtde_cnpjs}'),
    ('qtde_empresas', '{qtde_empresas}'),
    ('qtde_socios', '{qtde_socios}'),
    ('versao_script', '1.0'),
    ('banco_dados', 'PostgreSQL');
    """
    
    executar_sql(engine, sql)

# ============ FUNÇÃO PRINCIPAL ============

def main():
    """Função principal que executa todo o processo"""
    
    print("=" * 60)
    print("IMPORTAÇÃO UNIFICADA CNPJ PARA POSTGRESQL")
    print("=" * 60)
    
    # Verificar se os arquivos existem
    if not os.path.exists(pasta_compactados):
        print(f"ERRO: Pasta {pasta_compactados} não encontrada!")
        print("Baixe os arquivos da Receita Federal primeiro.")
        sys.exit(1)
    
    # Confirmar execução
    print("\nEste processo irá:")
    print("1. Descompactar arquivos ZIP")
    print("2. Criar banco de dados PostgreSQL")
    print("3. Importar dados do CNPJ")
    print("4. Criar links e relacionamentos")
    print("5. Criar índices e otimizações")
    print("\nTempo estimado: 4-6 horas")
    print(f"Espaço necessário: ~50GB")
    
    resp = input("\nDeseja continuar? (y/n): ")
    if resp.lower() != 'y':
        print("Operação cancelada.")
        sys.exit(0)
    
    inicio = time.time()
    
    try:
        # Criar engine PostgreSQL
        print("\n[1/10] Conectando ao PostgreSQL...")
        engine = criar_engine_postgresql()
        
        # Criar schemas
        print("\n[2/10] Criando schemas...")
        criar_schemas(engine)
        
        # Descompactar arquivos
        print("\n[3/10] Descompactando arquivos...")
        descompactar_arquivos()
        
        # Criar tabelas principais
        print("\n[4/10] Criando estrutura das tabelas...")
        criar_tabelas_principais(engine)
        
        # Carregar tabelas de código
        print("\n[5/10] Carregando tabelas auxiliares...")
        carregar_tabela_codigo(engine, '.CNAECSV', 'cnae')
        carregar_tabela_codigo(engine, '.MOTICSV', 'motivo')
        carregar_tabela_codigo(engine, '.MUNICCSV', 'municipio')
        carregar_tabela_codigo(engine, '.NATJUCSV', 'natureza_juridica')
        carregar_tabela_codigo(engine, '.PAISCSV', 'pais')
        carregar_tabela_codigo(engine, '.QUALSCSV', 'qualificacao_socio')
        
        # Carregar dados principais
        print("\n[6/10] Importando dados principais...")
        
        colunas_empresas = ['cnpj_basico', 'razao_social', 'natureza_juridica',
                           'qualificacao_responsavel', 'capital_social_str',
                           'porte_empresa', 'ente_federativo_responsavel']
        
        colunas_estabelecimento = ['cnpj_basico', 'cnpj_ordem', 'cnpj_dv', 'matriz_filial',
                                  'nome_fantasia', 'situacao_cadastral', 'data_situacao_cadastral',
                                  'motivo_situacao_cadastral', 'nome_cidade_exterior', 'pais',
                                  'data_inicio_atividades', 'cnae_fiscal', 'cnae_fiscal_secundaria',
                                  'tipo_logradouro', 'logradouro', 'numero', 'complemento', 'bairro',
                                  'cep', 'uf', 'municipio', 'ddd1', 'telefone1', 'ddd2', 'telefone2',
                                  'ddd_fax', 'fax', 'correio_eletronico', 'situacao_especial',
                                  'data_situacao_especial']
        
        colunas_socios = ['cnpj_basico', 'identificador_de_socio', 'nome_socio', 'cnpj_cpf_socio',
                         'qualificacao_socio', 'data_entrada_sociedade', 'pais', 'representante_legal',
                         'nome_representante', 'qualificacao_representante_legal', 'faixa_etaria']
        
        colunas_simples = ['cnpj_basico', 'opcao_simples', 'data_opcao_simples', 'data_exclusao_simples',
                          'opcao_mei', 'data_opcao_mei', 'data_exclusao_mei']
        
        carregar_arquivo_tipo(engine, 'empresas', '.EMPRECSV', colunas_empresas)
        carregar_arquivo_tipo(engine, 'estabelecimento', '.ESTABELE', colunas_estabelecimento)
        carregar_arquivo_tipo(engine, 'socios', '.SOCIOCSV', colunas_socios)
        carregar_arquivo_tipo(engine, 'simples', '.SIMPLES.CSV.*', colunas_simples)
        
        # Atualizar tabela de sócios
        print("\n[7/10] Atualizando tabela de sócios...")
        atualizar_tabela_socios(engine)
        
        # Criar índices
        print("\n[8/10] Criando índices...")
        criar_indices_principais(engine)
        
        # Processar endereços, telefones e emails
        print("\n[9/10] Processando links ETE...")
        processar_enderecos(engine)
        processar_telefones(engine)
        processar_emails(engine)
        criar_links_ete(engine)
        
        # Criar tabelas de rede
        print("\n[10/10] Criando rede de relacionamentos...")
        criar_tabela_ligacao(engine)
        criar_tabela_busca(engine)
        criar_views_auxiliares(engine)
        adicionar_estatisticas(engine)
        
        # Análise e vacuum
        print("\nOtimizando banco de dados...")
        with engine.begin() as conn:
            conn.execute(text("ANALYZE;"))
        
        tempo_total = time.time() - inicio
        horas = int(tempo_total // 3600)
        minutos = int((tempo_total % 3600) // 60)
        
        print("\n" + "=" * 60)
        print("IMPORTAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 60)
        print(f"Tempo total: {horas}h {minutos}min")
        
        # Mostrar estatísticas
        with engine.connect() as conn:
            stats = conn.execute(text("SELECT * FROM cnpj.estatisticas")).fetchone()
            print("\nEstatísticas:")
            print(f"  Empresas: {stats[0]:,}")
            print(f"  Estabelecimentos: {stats[1]:,}")
            print(f"  Sócios: {stats[2]:,}")
            print(f"  Ligações: {stats[4]:,}")
            print(f"  Links ETE: {stats[5]:,}")
        
    except Exception as e:
        print(f"\nERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        engine.dispose()

if __name__ == "__main__":
    # Configurar Dask
    dask.config.set({"num_workers": N_WORKERS})
    os.environ["DASK_NUM_WORKERS"] = str(N_WORKERS)
    os.environ["OMP_NUM_THREADS"] = str(DASK_THREADS)
    
    main()