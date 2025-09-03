#!/usr/bin/env python3
"""
Script para atualizar cidade e UF em planilha Excel baseado no CEP.
Utiliza a API ViaCEP para buscar informações de localização.
"""

import pandas as pd
import requests
import time
from typing import Dict, Optional, Tuple
import logging
from tqdm import tqdm
import json
import os
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("cep_update.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class CEPUpdater:
    """Classe para atualizar informações de CEP em planilhas Excel."""

    def __init__(self, cache_file: str = "cep_cache.json"):
        """
        Inicializa o atualizador de CEPs.

        Args:
            cache_file: Nome do arquivo de cache para CEPs já consultados
        """
        self.cache_file = cache_file
        self.cep_cache = self.load_cache()
        self.api_calls = 0
        self.api_errors = 0

    def load_cache(self) -> Dict:
        """Carrega o cache de CEPs do arquivo."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    logger.info(f"Cache carregado com {len(json.load(f))} CEPs")
                    f.seek(0)
                    return json.load(f)
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
        Busca informações de um CEP na API ViaCEP.

        Args:
            cep: CEP a ser consultado (apenas números)

        Returns:
            Dicionário com informações do CEP ou None se não encontrado
        """
        # Remove caracteres não numéricos
        cep_limpo = "".join(filter(str.isdigit, str(cep)))

        # Valida o CEP
        if len(cep_limpo) != 8:
            logger.debug(f"CEP inválido: {cep}")
            return None

        # Verifica o cache primeiro
        if cep_limpo in self.cep_cache:
            logger.debug(f"CEP {cep_limpo} encontrado no cache")
            return self.cep_cache[cep_limpo]

        # Busca na API
        try:
            url = f"https://viacep.com.br/ws/{cep_limpo}/json/"
            response = requests.get(url, timeout=5)
            self.api_calls += 1

            if response.status_code == 200:
                data = response.json()

                # Verifica se o CEP existe
                if "erro" not in data:
                    # Armazena no cache
                    self.cep_cache[cep_limpo] = data
                    logger.debug(
                        f"CEP {cep_limpo} encontrado: {data.get('localidade')}/{data.get('uf')}"
                    )
                    return data
                else:
                    logger.debug(f"CEP {cep_limpo} não existe na base")
                    self.cep_cache[cep_limpo] = None
                    return None
            else:
                logger.warning(
                    f"Erro na API para CEP {cep_limpo}: Status {response.status_code}"
                )
                self.api_errors += 1
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão para CEP {cep_limpo}: {e}")
            self.api_errors += 1
            return None
        except Exception as e:
            logger.error(f"Erro inesperado para CEP {cep_limpo}: {e}")
            self.api_errors += 1
            return None

    def processar_planilha(self, arquivo_entrada: str, arquivo_saida: str = None):
        """
        Processa a planilha Excel atualizando cidade e UF baseado no CEP.

        Args:
            arquivo_entrada: Caminho do arquivo Excel de entrada
            arquivo_saida: Caminho do arquivo de saída (se None, sobrescreve o original)
        """
        if arquivo_saida is None:
            # Cria um nome de arquivo de saída com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_base = os.path.splitext(arquivo_entrada)[0]
            arquivo_saida = f"{nome_base}_atualizado_{timestamp}.xlsx"

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
                        # Atualiza cidade e UF
                        df.at[idx, "cidade"] = info_cep.get("localidade", "")
                        df.at[idx, "uf"] = info_cep.get("uf", "")
                        atualizadas += 1
                    else:
                        erros += 1

                    # Pequena pausa para não sobrecarregar a API
                    # (ViaCEP não tem limite oficial, mas é bom ser respeitoso)
                    if self.api_calls % 10 == 0 and self.api_calls > 0:
                        time.sleep(0.1)

                    # Salva cache periodicamente
                    if self.api_calls % 100 == 0 and self.api_calls > 0:
                        self.save_cache()

                    pbar.update(1)

            # Salva a planilha atualizada
            logger.info(f"Salvando planilha atualizada: {arquivo_saida}")
            df.to_excel(arquivo_saida, index=False)

            # Salva o cache final
            self.save_cache()

            # Estatísticas finais
            logger.info("=" * 50)
            logger.info("RESUMO DO PROCESSAMENTO:")
            logger.info(f"Total de linhas: {len(df)}")
            logger.info(f"Linhas processadas: {len(linhas_processar)}")
            logger.info(f"Linhas atualizadas: {atualizadas}")
            logger.info(f"CEPs não encontrados: {erros}")
            logger.info(f"Chamadas à API: {self.api_calls}")
            logger.info(f"Erros de API: {self.api_errors}")
            logger.info(f"CEPs em cache: {len(self.cep_cache)}")
            logger.info(f"Arquivo salvo: {arquivo_saida}")
            logger.info("=" * 50)

        except Exception as e:
            logger.error(f"Erro ao processar planilha: {e}")
            raise


def main():
    """Função principal do script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Atualiza cidade e UF em planilha Excel baseado no CEP"
    )
    parser.add_argument("arquivo_entrada", help="Caminho do arquivo Excel de entrada")
    parser.add_argument(
        "-o",
        "--output",
        dest="arquivo_saida",
        help="Caminho do arquivo de saída (opcional)",
    )
    parser.add_argument(
        "-c",
        "--cache",
        default="cep_cache.json",
        help="Arquivo de cache para CEPs (padrão: cep_cache.json)",
    )
    parser.add_argument(
        "--limpar-cache", action="store_true", help="Limpa o cache antes de processar"
    )

    args = parser.parse_args()

    # Limpa cache se solicitado
    if args.limpar_cache and os.path.exists(args.cache):
        os.remove(args.cache)
        logger.info("Cache limpo")

    # Cria o atualizador e processa a planilha
    updater = CEPUpdater(cache_file=args.cache)
    updater.processar_planilha(args.arquivo_entrada, args.arquivo_saida)


if __name__ == "__main__":
    main()
