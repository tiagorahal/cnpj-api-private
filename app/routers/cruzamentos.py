"""
app/routers/cruzamentos.py
Router completo para cruzamentos de dados - PostgreSQL
"""

from fastapi import APIRouter, Depends, Query, HTTPException
import os
import re
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

# Importa as dependências de autenticação
from ..auth.dependencies import get_current_user, check_and_update_rate_limit

load_dotenv()

# Configuração do banco de dados
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cnpj_rede")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, future=True, pool_size=20, max_overflow=40)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

router = APIRouter()

# ============ FUNÇÕES AUXILIARES ============

async def require_active_user(user: dict = Depends(get_current_user)):
    """Requer usuário ativo (plano pago ou ilimitado)"""
    if user['is_active'] not in [1, 2]:
        raise HTTPException(403, "Acesso restrito a usuários ativos (planos limitados ou ilimitados).")
    return user

def normalize_email(email: str) -> str:
    """Normaliza email para busca"""
    return email.strip().lower()

def normalize_phone(ddd: str, phone: str) -> str:
    """Normaliza telefone removendo formatação"""
    full = (ddd or "") + (phone or "")
    return re.sub(r'\D', '', full)

# ============ ENDPOINTS DE COMPARTILHAMENTO ============

@router.get("/enderecos/compartilhados")
async def cnpjs_por_endereco(
    endereco: str, 
    user: dict = Depends(require_active_user)
):
    """Retorna CNPJs que compartilham o mesmo endereço"""
    await check_and_update_rate_limit(user, qtd_reqs=1)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id1 FROM links.link_ete WHERE id2 = :id2 AND descricao = 'end'"),
            {"id2": f"EN_{endereco}"}
        )
        rows = result.fetchall()
        cnpjs = [row[0].replace("PJ_", "") for row in rows if row[0].startswith("PJ_")]
    
    return {
        "endereco": endereco,
        "total": len(cnpjs),
        "cnpjs": cnpjs
    }

@router.get("/emails/compartilhados")
async def emails_compartilhados(
    email: str,
    user: dict = Depends(require_active_user)
):
    """Retorna CNPJs que compartilham o mesmo email"""
    await check_and_update_rate_limit(user, qtd_reqs=1)
    
    normalized_email = normalize_email(email)
    id2 = f"EM_{normalized_email}"
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id1 FROM links.link_ete WHERE id2 = :id2 AND descricao = 'email'"),
            {"id2": id2}
        )
        rows = result.fetchall()
        cnpjs = []
        for row in rows:
            if row[0].startswith('PJ_'):
                cnpjs.append(row[0][3:])
    
    return {
        "email": normalized_email,
        "total": len(cnpjs),
        "cnpjs": cnpjs
    }

@router.get("/telefones/compartilhados")
async def telefones_compartilhados(
    ddd: str = Query(..., description="DDD do telefone"),
    telefone: str = Query(..., description="Número do telefone"),
    user: dict = Depends(require_active_user)
):
    """Retorna CNPJs que compartilham o mesmo telefone"""
    await check_and_update_rate_limit(user, qtd_reqs=1)
    
    normalized_phone = normalize_phone(ddd, telefone)
    id2 = f"TE_{normalized_phone}"
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id1 FROM links.link_ete WHERE id2 = :id2 AND descricao = 'tel'"),
            {"id2": id2}
        )
        rows = result.fetchall()
        cnpjs = []
        for row in rows:
            if row[0].startswith('PJ_'):
                cnpjs.append(row[0][3:])
    
    return {
        "telefone": normalized_phone,
        "ddd": ddd,
        "numero": telefone,
        "total": len(cnpjs),
        "cnpjs": cnpjs
    }

# ============ ENDPOINTS DE DUPLICADOS ============

@router.get("/enderecos/duplicados")
async def enderecos_duplicados(
    minimo: int = Query(2, ge=2, description="Quantidade mínima de CNPJs por endereço"),
    limite: int = Query(100, ge=1, le=1000, description="Limite de resultados"),
    user: dict = Depends(require_active_user)
):
    """Lista endereços compartilhados por múltiplos CNPJs"""
    await check_and_update_rate_limit(user, qtd_reqs=1)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT id2, valor 
                FROM links.link_ete 
                WHERE descricao = 'end' AND valor >= :minimo
                ORDER BY valor DESC
                LIMIT :limite
            """),
            {"minimo": minimo, "limite": limite}
        )
        rows = result.fetchall()
        dados = []
        for row in rows:
            endereco = row[0][3:] if row[0].startswith('EN_') else row[0]
            dados.append({
                "endereco": endereco,
                "qtd_cnpjs": row[1]
            })
    
    return {
        "total_encontrados": len(dados),
        "filtro_minimo": minimo,
        "enderecos_duplicados": dados
    }

@router.get("/telefones/duplicados")
async def telefones_duplicados(
    minimo: int = Query(2, ge=2, description="Quantidade mínima de CNPJs por telefone"),
    limite: int = Query(100, ge=1, le=1000, description="Limite de resultados"),
    user: dict = Depends(require_active_user)
):
    """Lista telefones compartilhados por múltiplos CNPJs"""
    await check_and_update_rate_limit(user, qtd_reqs=1)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT id2, valor 
                FROM links.link_ete 
                WHERE descricao = 'tel' AND valor >= :minimo
                ORDER BY valor DESC
                LIMIT :limite
            """),
            {"minimo": minimo, "limite": limite}
        )
        rows = result.fetchall()
        dados = []
        for row in rows:
            telefone = row[0][3:] if row[0].startswith('TE_') else row[0]
            dados.append({
                "telefone": telefone,
                "qtd_cnpjs": row[1]
            })
    
    return {
        "total_encontrados": len(dados),
        "filtro_minimo": minimo,
        "telefones_duplicados": dados
    }

@router.get("/emails/duplicados")
async def emails_duplicados(
    minimo: int = Query(2, ge=2, description="Quantidade mínima de CNPJs por email"),
    limite: int = Query(100, ge=1, le=1000, description="Limite de resultados"),
    user: dict = Depends(require_active_user)
):
    """Lista emails compartilhados por múltiplos CNPJs"""
    await check_and_update_rate_limit(user, qtd_reqs=1)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT id2, valor 
                FROM links.link_ete 
                WHERE descricao = 'email' AND valor >= :minimo
                ORDER BY valor DESC
                LIMIT :limite
            """),
            {"minimo": minimo, "limite": limite}
        )
        rows = result.fetchall()
        dados = []
        for row in rows:
            email = row[0][3:] if row[0].startswith('EM_') else row[0]
            dados.append({
                "email": email,
                "qtd_cnpjs": row[1]
            })
    
    return {
        "total_encontrados": len(dados),
        "filtro_minimo": minimo,
        "emails_duplicados": dados
    }

# ============ VÍNCULOS E REDE ============

@router.get("/vinculos/{cnpj}")
async def vinculos_do_cnpj(
    cnpj: str,
    user: dict = Depends(require_active_user)
):
    """Retorna todos os vínculos (endereço, telefone, email, societários) de um CNPJ"""
    await check_and_update_rate_limit(user, qtd_reqs=1)
    
    # Remove formatação do CNPJ
    cnpj_limpo = re.sub(r'\D', '', cnpj)
    
    async with AsyncSessionLocal() as session:
        # Busca vínculos ETE (endereço, telefone, email)
        result = await session.execute(
            text("SELECT id2, descricao, valor FROM links.link_ete WHERE id1 = :id1"),
            {"id1": f"PJ_{cnpj_limpo}"}
        )
        rows_ete = result.fetchall()
        
        # Busca ligações societárias (saída - onde o CNPJ é origem)
        result = await session.execute(
            text("""
                SELECT id2, descricao, comentario 
                FROM rede.ligacao 
                WHERE id1 = :id1
                LIMIT 100
            """),
            {"id1": f"PJ_{cnpj_limpo}"}
        )
        rows_ligacao_saida = result.fetchall()
        
        # Busca ligações societárias (entrada - onde o CNPJ é destino)
        result = await session.execute(
            text("""
                SELECT id1, descricao, comentario 
                FROM rede.ligacao 
                WHERE id2 = :id2
                LIMIT 100
            """),
            {"id2": f"PJ_{cnpj_limpo}"}
        )
        rows_ligacao_entrada = result.fetchall()
        
        # Processa vínculos ETE
        vinculos_ete = []
        for row in rows_ete:
            tipo = row[1]
            valor_id = row[0]
            
            # Remove prefixo do ID
            if valor_id.startswith('EN_'):
                dado = valor_id[3:]
                tipo_vinculo = "endereco"
            elif valor_id.startswith('TE_'):
                dado = valor_id[3:]
                tipo_vinculo = "telefone"
            elif valor_id.startswith('EM_'):
                dado = valor_id[3:]
                tipo_vinculo = "email"
            else:
                dado = valor_id
                tipo_vinculo = tipo
            
            vinculos_ete.append({
                "tipo": tipo_vinculo,
                "dado": dado,
                "compartilhado_por": row[2]
            })
        
        # Processa ligações societárias de saída
        ligacoes_saida = []
        for row in rows_ligacao_saida:
            destino = row[0]
            tipo = row[1]
            base = row[2]
            ligacoes_saida.append({
                "destino": destino,
                "tipo": tipo,
                "base": base,
                "direcao": "saida"
            })
        
        # Processa ligações societárias de entrada
        ligacoes_entrada = []
        for row in rows_ligacao_entrada:
            origem = row[0]
            tipo = row[1]
            base = row[2]
            ligacoes_entrada.append({
                "origem": origem,
                "tipo": tipo,
                "base": base,
                "direcao": "entrada"
            })
    
    return {
        "cnpj": cnpj_limpo,
        "vinculos_ete": vinculos_ete,
        "ligacoes_societarias": {
            "saida": ligacoes_saida[:50],  # Limita a 50
            "entrada": ligacoes_entrada[:50],  # Limita a 50
            "total_saida": len(ligacoes_saida),
            "total_entrada": len(ligacoes_entrada)
        }
    }

@router.get("/rede/{cnpj}")
async def rede_do_cnpj(
    cnpj: str,
    nivel: int = Query(1, ge=1, le=3, description="Nível de profundidade da rede"),
    user: dict = Depends(require_active_user)
):
    """Retorna a rede de relacionamentos de um CNPJ até o nível especificado"""
    # Rate limit baseado no nível de profundidade
    await check_and_update_rate_limit(user, qtd_reqs=nivel)
    
    cnpj_limpo = re.sub(r'\D', '', cnpj)
    
    async with AsyncSessionLocal() as session:
        nodes = set()
        edges = []
        visitados = set()
        
        async def buscar_ligacoes(id_origem, nivel_atual):
            if nivel_atual > nivel or id_origem in visitados:
                return
            
            visitados.add(id_origem)
            nodes.add(id_origem)
            
            # Busca ligações de saída
            result = await session.execute(
                text("""
                    SELECT id2, descricao 
                    FROM rede.ligacao 
                    WHERE id1 = :id1
                    LIMIT 50
                """),
                {"id1": id_origem}
            )
            rows_saida = result.fetchall()
            
            # Busca ligações de entrada
            result = await session.execute(
                text("""
                    SELECT id1, descricao 
                    FROM rede.ligacao 
                    WHERE id2 = :id2
                    LIMIT 50
                """),
                {"id2": id_origem}
            )
            rows_entrada = result.fetchall()
            
            # Processa ligações de saída
            for row in rows_saida:
                destino = row[0]
                tipo = row[1]
                nodes.add(destino)
                edge_id = f"{id_origem}->{destino}"
                edges.append({
                    "id": edge_id,
                    "origem": id_origem,
                    "destino": destino,
                    "tipo": tipo,
                    "direcao": "saida"
                })
                
                if nivel_atual < nivel:
                    await buscar_ligacoes(destino, nivel_atual + 1)
            
            # Processa ligações de entrada
            for row in rows_entrada:
                origem = row[0]
                tipo = row[1]
                nodes.add(origem)
                edge_id = f"{origem}->{id_origem}"
                edges.append({
                    "id": edge_id,
                    "origem": origem,
                    "destino": id_origem,
                    "tipo": tipo,
                    "direcao": "entrada"
                })
                
                if nivel_atual < nivel:
                    await buscar_ligacoes(origem, nivel_atual + 1)
        
        # Inicia busca recursiva
        await buscar_ligacoes(f"PJ_{cnpj_limpo}", 1)
        
        # Formata nodes para incluir tipo e nome
        nodes_formatados = []
        for node in nodes:
            if node.startswith("PJ_"):
                tipo_node = "Pessoa Jurídica"
                label = node[3:]
            elif node.startswith("PF_"):
                tipo_node = "Pessoa Física"
                label = node[3:]
            elif node.startswith("PE_"):
                tipo_node = "Pessoa Estrangeira"
                label = node[3:]
            else:
                tipo_node = "Desconhecido"
                label = node
            
            nodes_formatados.append({
                "id": node,
                "tipo": tipo_node,
                "label": label
            })
        
        # Remove duplicatas de edges
        edges_unicos = []
        edges_ids = set()
        for edge in edges:
            if edge["id"] not in edges_ids:
                edges_ids.add(edge["id"])
                edges_unicos.append(edge)
    
    return {
        "cnpj_origem": cnpj_limpo,
        "nivel_profundidade": nivel,
        "total_nodes": len(nodes_formatados),
        "total_edges": len(edges_unicos),
        "nodes": nodes_formatados,
        "edges": edges_unicos
    }

# ============ ANÁLISES AVANÇADAS ============

@router.get("/analise/grupo_economico/{cnpj}")
async def analisar_grupo_economico(
    cnpj: str,
    user: dict = Depends(require_active_user)
):
    """Analisa o grupo econômico de um CNPJ através de conexões diretas e indiretas"""
    await check_and_update_rate_limit(user, qtd_reqs=5)
    
    cnpj_limpo = re.sub(r'\D', '', cnpj)
    
    async with AsyncSessionLocal() as session:
        grupo = {
            "empresas_controladas": [],
            "empresas_controladoras": [],
            "socios_pf": [],
            "socios_pj": [],
            "enderecos_compartilhados": [],
            "telefones_compartilhados": [],
            "emails_compartilhados": []
        }
        
        # Busca empresas onde o CNPJ é sócio (controladas)
        result = await session.execute(
            text("""
                SELECT DISTINCT id2, descricao 
                FROM rede.ligacao 
                WHERE id1 = :id1 
                  AND id2 LIKE 'PJ_%'
                  AND descricao NOT IN ('filial')
                LIMIT 100
            """),
            {"id1": f"PJ_{cnpj_limpo}"}
        )
        for row in result.fetchall():
            grupo["empresas_controladas"].append({
                "cnpj": row[0][3:] if row[0].startswith('PJ_') else row[0],
                "tipo_vinculo": row[1]
            })
        
        # Busca empresas que são sócias do CNPJ (controladoras)
        result = await session.execute(
            text("""
                SELECT DISTINCT id1, descricao 
                FROM rede.ligacao 
                WHERE id2 = :id2 
                  AND id1 LIKE 'PJ_%'
                  AND descricao NOT IN ('filial')
                LIMIT 100
            """),
            {"id2": f"PJ_{cnpj_limpo}"}
        )
        for row in result.fetchall():
            grupo["empresas_controladoras"].append({
                "cnpj": row[0][3:] if row[0].startswith('PJ_') else row[0],
                "tipo_vinculo": row[1]
            })
        
        # Busca sócios pessoas físicas
        result = await session.execute(
            text("""
                SELECT DISTINCT id1, descricao 
                FROM rede.ligacao 
                WHERE id2 = :id2 
                  AND id1 LIKE 'PF_%'
                LIMIT 100
            """),
            {"id2": f"PJ_{cnpj_limpo}"}
        )
        for row in result.fetchall():
            grupo["socios_pf"].append({
                "socio": row[0][3:] if row[0].startswith('PF_') else row[0],
                "tipo_vinculo": row[1]
            })
        
        # Busca sócios pessoas jurídicas
        result = await session.execute(
            text("""
                SELECT DISTINCT id1, descricao 
                FROM rede.ligacao 
                WHERE id2 = :id2 
                  AND id1 LIKE 'PJ_%'
                  AND descricao IN ('Sócio', 'Administrador', 'Diretor', 'Presidente')
                LIMIT 100
            """),
            {"id2": f"PJ_{cnpj_limpo}"}
        )
        for row in result.fetchall():
            grupo["socios_pj"].append({
                "cnpj_socio": row[0][3:] if row[0].startswith('PJ_') else row[0],
                "tipo_vinculo": row[1]
            })
        
        # Busca endereços compartilhados
        result = await session.execute(
            text("""
                SELECT DISTINCT le2.id1, le1.id2
                FROM links.link_ete le1
                JOIN links.link_ete le2 ON le1.id2 = le2.id2
                WHERE le1.id1 = :id1 
                  AND le1.descricao = 'end'
                  AND le2.id1 != :id1
                  AND le2.id1 LIKE 'PJ_%'
                LIMIT 50
            """),
            {"id1": f"PJ_{cnpj_limpo}"}
        )
        for row in result.fetchall():
            grupo["enderecos_compartilhados"].append({
                "cnpj": row[0][3:] if row[0].startswith('PJ_') else row[0],
                "endereco": row[1][3:] if row[1].startswith('EN_') else row[1]
            })
        
        # Busca telefones compartilhados
        result = await session.execute(
            text("""
                SELECT DISTINCT le2.id1, le1.id2
                FROM links.link_ete le1
                JOIN links.link_ete le2 ON le1.id2 = le2.id2
                WHERE le1.id1 = :id1 
                  AND le1.descricao = 'tel'
                  AND le2.id1 != :id1
                  AND le2.id1 LIKE 'PJ_%'
                LIMIT 50
            """),
            {"id1": f"PJ_{cnpj_limpo}"}
        )
        for row in result.fetchall():
            grupo["telefones_compartilhados"].append({
                "cnpj": row[0][3:] if row[0].startswith('PJ_') else row[0],
                "telefone": row[1][3:] if row[1].startswith('TE_') else row[1]
            })
        
        # Busca emails compartilhados
        result = await session.execute(
            text("""
                SELECT DISTINCT le2.id1, le1.id2
                FROM links.link_ete le1
                JOIN links.link_ete le2 ON le1.id2 = le2.id2
                WHERE le1.id1 = :id1 
                  AND le1.descricao = 'email'
                  AND le2.id1 != :id1
                  AND le2.id1 LIKE 'PJ_%'
                LIMIT 50
            """),
            {"id1": f"PJ_{cnpj_limpo}"}
        )
        for row in result.fetchall():
            grupo["emails_compartilhados"].append({
                "cnpj": row[0][3:] if row[0].startswith('PJ_') else row[0],
                "email": row[1][3:] if row[1].startswith('EM_') else row[1]
            })
        
        # Calcula totais
        totais = {
            "total_empresas_controladas": len(grupo["empresas_controladas"]),
            "total_empresas_controladoras": len(grupo["empresas_controladoras"]),
            "total_socios_pf": len(grupo["socios_pf"]),
            "total_socios_pj": len(grupo["socios_pj"]),
            "total_enderecos_compartilhados": len(grupo["enderecos_compartilhados"]),
            "total_telefones_compartilhados": len(grupo["telefones_compartilhados"]),
            "total_emails_compartilhados": len(grupo["emails_compartilhados"])
        }
    
    return {
        "cnpj_analisado": cnpj_limpo,
        "totais": totais,
        "detalhes": grupo
    }