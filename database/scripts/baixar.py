import requests
from tqdm import tqdm

BASE_URL = "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/2025-06/"

arquivos = [
    "Cnaes.zip",
    "Empresas0.zip", "Empresas1.zip", "Empresas2.zip", "Empresas3.zip", "Empresas4.zip",
    "Empresas5.zip", "Empresas6.zip", "Empresas7.zip", "Empresas8.zip", "Empresas9.zip",
    "Estabelecimentos0.zip", "Estabelecimentos1.zip", "Estabelecimentos2.zip", "Estabelecimentos3.zip",
    "Estabelecimentos4.zip", "Estabelecimentos5.zip", "Estabelecimentos6.zip", "Estabelecimentos7.zip",
    "Estabelecimentos8.zip", "Estabelecimentos9.zip",
    "Motivos.zip", "Municipios.zip", "Naturezas.zip", "Paises.zip", "Qualificacoes.zip",
    "Simples.zip",
    "Socios0.zip", "Socios1.zip", "Socios2.zip", "Socios3.zip", "Socios4.zip",
    "Socios5.zip", "Socios6.zip", "Socios7.zip", "Socios8.zip", "Socios9.zip"
]

for arquivo in arquivos:
    url = BASE_URL + arquivo
    print(f"\nBaixando {arquivo} ...")
    try:
        # Faz a requisição
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            with open(arquivo, 'wb') as f, tqdm(
                total=total, unit='B', unit_scale=True, unit_divisor=1024, desc=arquivo
            ) as bar:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    bar.update(len(chunk))
        print(f"✔️  {arquivo} baixado com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao baixar {arquivo}: {e}")
