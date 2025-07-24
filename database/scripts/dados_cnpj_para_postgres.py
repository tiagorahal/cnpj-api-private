# -*- coding: utf-8 -*-
"""
Rotina para converter os arquivos CSV do CNPJ para uma base
PostgreSQL. Baseado no script original que gerava um banco
SQLite.
"""

import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
import glob
import time
import dask.dataframe as dd
import os
import sys
import zipfile

# Diretórios de entrada/saída
pasta_compactados = r"dados-publicos-zip"
pasta_saida = r"dados-publicos"

# Dados de conexão com o PostgreSQL obtidos via variáveis de ambiente
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "cnpj")

engine_url = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
    f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)
engine = create_engine(engine_url)

bApagaDescompactadosAposUso = True

arquivos_zip = list(glob.glob(os.path.join(pasta_compactados, "*.zip")))
if not arquivos_zip:
    print("Nenhum arquivo zip encontrado em", pasta_compactados)
    sys.exit(1)

print("Início:", time.asctime())
for arq in arquivos_zip:
    print(time.asctime(), "descompactando", arq)
    with zipfile.ZipFile(arq, "r") as zip_ref:
        zip_ref.extractall(pasta_saida)

# detecta a data de referência dos arquivos
ref_arq = glob.glob(os.path.join(pasta_saida, "*.EMPRECSV"))[0]
ref_part = os.path.basename(ref_arq).split(".")[2]
if ref_part.startswith("D") and len(ref_part) == len("D30610"):
    dataReferencia = f"{ref_part[4:6]}/{ref_part[2:4]}/202{ref_part[1]}"
else:
    dataReferencia = "00/00/0000"

# Função auxiliar para criar e carregar tabelas pequenas
def carrega_tabela_codigo(extensao, nome_tabela):
    arquivo = glob.glob(os.path.join(pasta_saida, f"*{extensao}"))[0]
    print("carregando", arquivo, "na tabela", nome_tabela)
    df = pd.read_csv(
        arquivo,
        dtype=str,
        sep=";",
        encoding="latin1",
        header=None,
        names=["codigo", "descricao"],
    )
    df.to_sql(nome_tabela, engine, if_exists="replace", index=False)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE INDEX idx_{nome_tabela} ON {nome_tabela}(codigo)"))
    if bApagaDescompactadosAposUso:
        os.remove(arquivo)

carrega_tabela_codigo(".CNAECSV", "cnae")
carrega_tabela_codigo(".MOTICSV", "motivo")
carrega_tabela_codigo(".MUNICCSV", "municipio")
carrega_tabela_codigo(".NATJUCSV", "natureza_juridica")
carrega_tabela_codigo(".PAISCSV", "pais")
carrega_tabela_codigo(".QUALSCSV", "qualificacao_socio")

# Definição das colunas das tabelas grandes
colunas_empresas = [
    "cnpj_basico",
    "razao_social",
    "natureza_juridica",
    "qualificacao_responsavel",
    "capital_social_str",
    "porte_empresa",
    "ente_federativo_responsavel",
]

colunas_estabelecimento = [
    "cnpj_basico",
    "cnpj_ordem",
    "cnpj_dv",
    "matriz_filial",
    "nome_fantasia",
    "situacao_cadastral",
    "data_situacao_cadastral",
    "motivo_situacao_cadastral",
    "nome_cidade_exterior",
    "pais",
    "data_inicio_atividades",
    "cnae_fiscal",
    "cnae_fiscal_secundaria",
    "tipo_logradouro",
    "logradouro",
    "numero",
    "complemento",
    "bairro",
    "cep",
    "uf",
    "municipio",
    "ddd1",
    "telefone1",
    "ddd2",
    "telefone2",
    "ddd_fax",
    "fax",
    "correio_eletronico",
    "situacao_especial",
    "data_situacao_especial",
]

colunas_socios = [
    "cnpj_basico",
    "identificador_de_socio",
    "nome_socio",
    "cnpj_cpf_socio",
    "qualificacao_socio",
    "data_entrada_sociedade",
    "pais",
    "representante_legal",
    "nome_representante",
    "qualificacao_representante_legal",
    "faixa_etaria",
]

colunas_simples = [
    "cnpj_basico",
    "opcao_simples",
    "data_opcao_simples",
    "data_exclusao_simples",
    "opcao_mei",
    "data_opcao_mei",
    "data_exclusao_mei",
]

# Criação das tabelas vazias
with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS empresas"))
    conn.execute(text("DROP TABLE IF EXISTS estabelecimento"))
    conn.execute(text("DROP TABLE IF EXISTS socios_original"))
    conn.execute(text("DROP TABLE IF EXISTS simples"))

pd.DataFrame(columns=colunas_empresas).to_sql("empresas", engine, index=False)
pd.DataFrame(columns=colunas_estabelecimento).to_sql("estabelecimento", engine, index=False)
pd.DataFrame(columns=colunas_socios).to_sql("socios_original", engine, index=False)
pd.DataFrame(columns=colunas_simples).to_sql("simples", engine, index=False)

# Função para carregar tabelas grandes usando Dask

def carrega_tipo(nome_tabela, padrao, colunas):
    arquivos = glob.glob(os.path.join(pasta_saida, f"*{padrao}"))
    for arq in arquivos:
        print("carregando:", arq, "em", nome_tabela)
        ddf = dd.read_csv(
            arq,
            sep=";",
            header=None,
            names=colunas,
            encoding="latin1",
            dtype=str,
            na_filter=None,
        )
        ddf.to_sql(nome_tabela, engine_url, if_exists="append", index=False)
        if bApagaDescompactadosAposUso:
            os.remove(arq)
        print("fim parcial...", time.asctime())

carrega_tipo("empresas", ".EMPRECSV", colunas_empresas)
carrega_tipo("estabelecimento", ".ESTABELE", colunas_estabelecimento)
carrega_tipo("socios_original", ".SOCIOCSV", colunas_socios)
carrega_tipo("simples", ".SIMPLES.CSV.*", colunas_simples)

# Ajustes e índices
ajustes_sql = """
ALTER TABLE empresas ADD COLUMN capital_social real;
UPDATE empresas SET capital_social = REPLACE(capital_social_str, ',', '.')::real;
ALTER TABLE empresas DROP COLUMN capital_social_str;
ALTER TABLE estabelecimento ADD COLUMN cnpj text;
UPDATE estabelecimento SET cnpj = cnpj_basico||cnpj_ordem||cnpj_dv;
CREATE INDEX idx_empresas_cnpj_basico ON empresas (cnpj_basico);
CREATE INDEX idx_empresas_razao_social ON empresas (razao_social);
CREATE INDEX idx_estabelecimento_cnpj_basico ON estabelecimento (cnpj_basico);
CREATE INDEX idx_estabelecimento_cnpj ON estabelecimento (cnpj);
CREATE INDEX idx_estabelecimento_nomefantasia ON estabelecimento (nome_fantasia);
CREATE INDEX idx_socios_original_cnpj_basico ON socios_original(cnpj_basico);
CREATE TABLE socios AS
    SELECT te.cnpj AS cnpj, ts.*
    FROM socios_original ts
    LEFT JOIN estabelecimento te ON te.cnpj_basico = ts.cnpj_basico
    WHERE te.matriz_filial='1';
DROP TABLE IF EXISTS socios_original;
CREATE INDEX idx_socios_cnpj ON socios(cnpj);
CREATE INDEX idx_socios_cnpj_cpf_socio ON socios(cnpj_cpf_socio);
CREATE INDEX idx_socios_nome_socio ON socios(nome_socio);
CREATE INDEX idx_socios_representante ON socios(representante_legal);
CREATE INDEX idx_socios_representante_nome ON socios(nome_representante);
CREATE INDEX idx_simples_cnpj_basico ON simples(cnpj_basico);
CREATE TABLE IF NOT EXISTS _referencia (
    referencia TEXT,
    valor TEXT
);
"""

with engine.begin() as conn:
    for stmt in ajustes_sql.strip().split(";"):
        if stmt.strip():
            print("executando:", stmt[:60], "...")
            conn.execute(text(stmt))

qtde_cnpjs = engine.execute(
    text("SELECT count(*) FROM estabelecimento")
).fetchone()[0]
with engine.begin() as conn:
    conn.execute(
        text("INSERT INTO _referencia (referencia, valor) VALUES (:r, :v)"),
        {"r": "CNPJ", "v": dataReferencia},
    )
    conn.execute(
        text("INSERT INTO _referencia (referencia, valor) VALUES (:r, :v)"),
        {"r": "cnpj_qtde", "v": str(qtde_cnpjs)},
    )

print("-" * 20)
print(
    f"Dados carregados no banco PostgreSQL '{POSTGRES_DB}'. Total de CNPJs: {qtde_cnpjs}"
)
print("FIM!!!", time.asctime())
