#!/usr/bin/env python3
"""
Script para atualizar cidade e UF em planilha Excel baseado no CEP.
Versão com suporte a múltiplas APIs de CEP com fallback automático.

APIs suportadas:
1. ViaCEP - https://viacep.com.br
2. AwesomeAPI - https://cep.awesomeapi.com.br
3. BrasilAPI - https://brasilapi.com.br
"""

import pandas as pd
import requests
import time
from typing import Dict, Optional, List, Tuple
import logging
from tqdm import tqdm
import json
import os
import shutil
from datetime import datetime
from abc import ABC, abstractmethod

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("cep_update_multi.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class CEPProvider(ABC):
    """Classe base abstrata para provedores de CEP."""

    def __init__(self, name: str):
        self.name = name
        self.success_count = 0
        self.error_count = 0
        self.total_time = 0

    @abstractmethod
    def buscar(self, cep: str) -> Optional[Dict]:
        """Busca informações do CEP."""
        pass

    def get_stats(self) -> Dict:
        """Retorna estatísticas do provedor."""
        return {
            "name": self.name,
            "success": self.success_count,
            "errors": self.error_count,
            "total": self.success_count + self.error_count,
            "success_rate": (
                self.success_count / (self.success_count + self.error_count)
                if (self.success_count + self.error_count) > 0
                else 0
            ),
            "avg_time": (
                self.total_time / self.success_count if self.success_count > 0 else 0
            ),
        }


class ViaCEPProvider(CEPProvider):
    """Provedor ViaCEP - Principal e mais confiável."""

    def __init__(self):
        super().__init__("ViaCEP")

    def buscar(self, cep: str) -> Optional[Dict]:
        """Busca CEP na API ViaCEP."""
        start_time = time.time()

        try:
            url = f"https://viacep.com.br/ws/{cep}/json/"
            response = requests.get(url, timeout=8)

            if response.status_code == 200:
                data = response.json()

                if "erro" not in data:
                    self.success_count += 1
                    self.total_time += time.time() - start_time

                    # Padroniza a resposta
                    return {
                        "cep": data.get("cep", ""),
                        "cidade": data.get("localidade", ""),
                        "uf": data.get("uf", ""),
                        "bairro": data.get("bairro", ""),
                        "logradouro": data.get("logradouro", ""),
                        "complemento": data.get("complemento", ""),
                        "ddd": data.get("ddd", ""),
                        "provider": self.name,
                    }

            self.error_count += 1
            return None

        except Exception as e:
            self.error_count += 1
            logger.debug(f"{self.name} erro para CEP {cep}: {str(e)}")
            return None


class AwesomeAPIProvider(CEPProvider):
    """Provedor AwesomeAPI - Backup secundário."""

    def __init__(self):
        super().__init__("AwesomeAPI")

    def buscar(self, cep: str) -> Optional[Dict]:
        """Busca CEP na AwesomeAPI."""
        start_time = time.time()

        try:
            url = f"https://cep.awesomeapi.com.br/json/{cep}"
            response = requests.get(url, timeout=8)

            if response.status_code == 200:
                data = response.json()

                # Verifica se encontrou o CEP
                if "status" not in data or data.get("status") != 400:
                    self.success_count += 1
                    self.total_time += time.time() - start_time

                    # Padroniza a resposta
                    return {
                        "cep": data.get("cep", ""),
                        "cidade": data.get("city", ""),
                        "uf": data.get("state", ""),
                        "bairro": data.get("district", ""),
                        "logradouro": data.get("address", ""),
                        "complemento": "",
                        "ddd": data.get("ddd", ""),
                        "provider": self.name,
                    }

            self.error_count += 1
            return None

        except Exception as e:
            self.error_count += 1
            logger.debug(f"{self.name} erro para CEP {cep}: {str(e)}")
            return None


class BrasilAPIProvider(CEPProvider):
    """Provedor BrasilAPI - Backup terciário."""

    def __init__(self):
        super().__init__("BrasilAPI")

    def buscar(self, cep: str) -> Optional[Dict]:
        """Busca CEP na BrasilAPI."""
        start_time = time.time()

        try:
            url = f"https://brasilapi.com.br/api/cep/v2/{cep}"
            response = requests.get(url, timeout=8)

            if response.status_code == 200:
                data = response.json()

                self.success_count += 1
                self.total_time += time.time() - start_time

                # Padroniza a resposta
                return {
                    "cep": data.get("cep", ""),
                    "cidade": data.get("city", ""),
                    "uf": data.get("state", ""),
                    "bairro": data.get("neighborhood", ""),
                    "logradouro": data.get("street", ""),
                    "complemento": "",
                    "ddd": "",  # BrasilAPI não retorna DDD
                    "provider": self.name,
                }

            self.error_count += 1
            return None

        except Exception as e:
            self.error_count += 1
            logger.debug(f"{self.name} erro para CEP {cep}: {str(e)}")
            return None


class CEPUpdaterMultiAPI:
    """Atualizador de CEPs com suporte a múltiplas APIs."""

    def __init__(self, cache_file: str = "cep_cache_multi.json"):
        """
        Inicializa o atualizador com múltiplas APIs.

        Args:
            cache_file: Nome do arquivo de cache para CEPs já consultados
        """
        self.cache_file = cache_file
        self.cep_cache = self.load_cache()

        # Inicializa os provedores em ordem de prioridade
        self.providers = [ViaCEPProvider(), AwesomeAPIProvider(), BrasilAPIProvider()]

        # Estatísticas gerais
        self.total_queries = 0
        self.cache_hits = 0
        self.api_successes = 0
        self.api_failures = 0

    def load_cache(self) -> Dict:
        """Carrega o cache de CEPs do arquivo."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    logger.info(f"Cache carregado com {len(cache_data)} CEPs")
                    return cache_data
            except Exception as e:
                logger.warning(f"Erro ao carregar cache: {e}")
                return {}
        return {}

    def save_cache(self):
        """Salva o cache de CEPs no arquivo."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cep_cache, f, ensure_ascii=False, indent=2)
            logger.info(f"Cache salvo com {len(self.cep_cache)} CEPs")
        except Exception as e:
            logger.error(f"Erro ao salvar cache: {e}")

    def buscar_cep(self, cep: str) -> Optional[Dict]:
        """
        Busca informações de um CEP usando múltiplas APIs com fallback.

        Args:
            cep: CEP a ser consultado (apenas números)

        Returns:
            Dicionário com informações do CEP ou None se não encontrado
        """
        self.total_queries += 1

        # Remove caracteres não numéricos
        cep_limpo = "".join(filter(str.isdigit, str(cep)))

        # Valida o CEP
        if len(cep_limpo) != 8:
            logger.debug(f"CEP inválido: {cep}")
            return None

        # Verifica o cache primeiro
        if cep_limpo in self.cep_cache:
            self.cache_hits += 1
            logger.debug(f"CEP {cep_limpo} encontrado no cache")
            return self.cep_cache[cep_limpo]

        # Tenta cada provedor em ordem
        for provider in self.providers:
            logger.debug(f"Tentando {provider.name} para CEP {cep_limpo}")

            result = provider.buscar(cep_limpo)

            if result:
                # Sucesso! Armazena no cache e retorna
                self.cep_cache[cep_limpo] = result
                self.api_successes += 1

                logger.info(
                    f"✅ CEP {cep_limpo} encontrado via {provider.name}: "
                    f"{result.get('cidade')}/{result.get('uf')}"
                )

                return result

            # Se falhou, tenta o próximo provedor
            logger.debug(f"{provider.name} falhou, tentando próximo...")

        # Se todos falharam
        logger.warning(f"❌ CEP {cep_limpo} não encontrado em nenhuma API")
        self.api_failures += 1
        self.cep_cache[cep_limpo] = None  # Cache negativo
        return None

    def processar_planilha(
        self, arquivo_entrada: str, arquivo_saida: str = None, criar_backup: bool = True
    ):
        """
        Processa a planilha Excel atualizando cidade e UF baseado no CEP.

        Args:
            arquivo_entrada: Caminho do arquivo Excel de entrada
            arquivo_saida: Caminho do arquivo de saída (se None, atualiza o arquivo original)
            criar_backup: Se True, cria backup antes de sobrescrever o original
        """
        # Define arquivo de saída
        atualizar_original = arquivo_saida is None
        arquivo_backup = None

        if atualizar_original:
            arquivo_saida = arquivo_entrada

            # Cria backup se solicitado
            if criar_backup:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_base = os.path.splitext(arquivo_entrada)[0]
                arquivo_backup = f"{nome_base}_backup_{timestamp}.xlsx"

                shutil.copy2(arquivo_entrada, arquivo_backup)
                logger.info(f"Backup criado: {arquivo_backup}")

        logger.info(f"Lendo arquivo: {arquivo_entrada}")

        try:
            # Lê a planilha
            df = pd.read_excel(arquivo_entrada)
            logger.info(f"Planilha carregada: {len(df)} linhas")

            # Identifica colunas necessárias
            colunas_necessarias = ["cep_encontrado", "cidade", "uf"]
            for col in colunas_necessarias:
                if col not in df.columns:
                    raise ValueError(f"Coluna '{col}' não encontrada na planilha")

            # Adiciona coluna para rastrear qual API foi usada (opcional)
            if "api_usada" not in df.columns:
                df["api_usada"] = ""

            # Conta linhas a serem processadas
            mask = (df["cep_encontrado"].notna()) & (
                (df["cidade"].isna()) | (df["uf"].isna())
            )
            linhas_processar = df[mask]

            logger.info(f"Linhas a processar: {len(linhas_processar)}")
            logger.info(
                f"Linhas completas (ignoradas): {len(df) - len(linhas_processar)}"
            )

            if len(linhas_processar) == 0:
                logger.info("Nenhuma linha precisa ser processada!")
                return

            # Processa as linhas com barra de progresso
            atualizadas = 0
            erros = 0

            with tqdm(total=len(linhas_processar), desc="Processando CEPs") as pbar:
                for idx in linhas_processar.index:
                    cep = df.at[idx, "cep_encontrado"]

                    # Busca informações do CEP
                    info_cep = self.buscar_cep(cep)

                    if info_cep:
                        # Atualiza cidade, UF e API usada
                        df.at[idx, "cidade"] = info_cep.get("cidade", "")
                        df.at[idx, "uf"] = info_cep.get("uf", "")
                        df.at[idx, "api_usada"] = info_cep.get("provider", "")
                        atualizadas += 1
                    else:
                        df.at[idx, "api_usada"] = "NÃO ENCONTRADO"
                        erros += 1

                    # Pequena pausa para não sobrecarregar as APIs
                    if self.total_queries % 10 == 0 and self.total_queries > 0:
                        time.sleep(0.1)

                    # Salva cache periodicamente
                    if self.total_queries % 100 == 0 and self.total_queries > 0:
                        self.save_cache()

                    pbar.update(1)

            # Salva a planilha atualizada
            if atualizar_original:
                logger.info(f"Atualizando arquivo original: {arquivo_saida}")
            else:
                logger.info(f"Salvando novo arquivo: {arquivo_saida}")
            df.to_excel(arquivo_saida, index=False)

            # Salva o cache final
            self.save_cache()

            # Estatísticas finais
            self.print_statistics(
                len(df),
                len(linhas_processar),
                atualizadas,
                erros,
                atualizar_original,
                arquivo_saida,
                arquivo_entrada,
                arquivo_backup,
            )

        except Exception as e:
            logger.error(f"Erro ao processar planilha: {e}")
            raise

    def print_statistics(
        self,
        total_linhas,
        linhas_processadas,
        atualizadas,
        erros,
        atualizar_original,
        arquivo_saida,
        arquivo_entrada,
        arquivo_backup,
    ):
        """Imprime estatísticas detalhadas do processamento."""

        logger.info("=" * 70)
        logger.info("RESUMO DO PROCESSAMENTO:")
        logger.info("-" * 70)

        # Estatísticas gerais
        logger.info(f"📊 DADOS DA PLANILHA:")
        logger.info(f"   Total de linhas: {total_linhas}")
        logger.info(f"   Linhas processadas: {linhas_processadas}")
        logger.info(f"   Linhas atualizadas: {atualizadas}")
        logger.info(f"   CEPs não encontrados: {erros}")

        # Estatísticas de cache e APIs
        logger.info(f"\n🔍 CONSULTAS:")
        logger.info(f"   Total de consultas: {self.total_queries}")
        logger.info(
            f"   Hits de cache: {self.cache_hits} "
            f"({self.cache_hits/self.total_queries*100:.1f}%)"
            if self.total_queries > 0
            else ""
        )
        logger.info(f"   Consultas às APIs: {self.api_successes + self.api_failures}")
        logger.info(f"   CEPs em cache: {len(self.cep_cache)}")

        # Estatísticas por provedor
        logger.info(f"\n📡 ESTATÍSTICAS POR API:")
        for provider in self.providers:
            stats = provider.get_stats()
            if stats["total"] > 0:
                logger.info(f"   {stats['name']}:")
                logger.info(f"      Sucessos: {stats['success']}")
                logger.info(f"      Falhas: {stats['errors']}")
                logger.info(f"      Taxa de sucesso: {stats['success_rate']*100:.1f}%")
                logger.info(f"      Tempo médio: {stats['avg_time']:.2f}s")

        # Arquivos
        logger.info(f"\n📁 ARQUIVOS:")
        if atualizar_original:
            logger.info(f"   ✅ Arquivo original atualizado: {arquivo_saida}")
            if arquivo_backup:
                logger.info(f"   📁 Backup salvo: {arquivo_backup}")
        else:
            logger.info(f"   📁 Novo arquivo: {arquivo_saida}")
            logger.info(f"   📁 Original preservado: {arquivo_entrada}")

        logger.info("=" * 70)


def main():
    """Função principal do script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Atualiza cidade e UF em planilha Excel usando múltiplas APIs de CEP"
    )
    parser.add_argument(
        "arquivo_entrada",
        help="Caminho do arquivo Excel de entrada (será atualizado diretamente)",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="arquivo_saida",
        help="Caminho do arquivo de saída (se especificado, preserva o original)",
    )
    parser.add_argument(
        "-c",
        "--cache",
        default="cep_cache_multi.json",
        help="Arquivo de cache para CEPs (padrão: cep_cache_multi.json)",
    )
    parser.add_argument(
        "--sem-backup",
        action="store_true",
        help="NÃO criar backup ao atualizar o arquivo original",
    )
    parser.add_argument(
        "--limpar-cache", action="store_true", help="Limpa o cache antes de processar"
    )

    args = parser.parse_args()

    # Limpa cache se solicitado
    if args.limpar_cache and os.path.exists(args.cache):
        os.remove(args.cache)
        logger.info("Cache limpo")

    # Define se deve criar backup
    criar_backup = not args.sem_backup and args.arquivo_saida is None

    # Cria o atualizador e processa a planilha
    updater = CEPUpdaterMultiAPI(cache_file=args.cache)
    updater.processar_planilha(
        args.arquivo_entrada, args.arquivo_saida, criar_backup=criar_backup
    )


if __name__ == "__main__":
    main()
