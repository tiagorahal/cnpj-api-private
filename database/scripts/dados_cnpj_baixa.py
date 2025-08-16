# -*- coding: utf-8 -*-
"""
lista relação de arquivos na página de dados públicos da receita federal
e faz o download
https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj
https://dadosabertos.rfb.gov.br/CNPJ/
http://200.152.38.155/CNPJ/
"""
from bs4 import BeautifulSoup
import requests, wget, os, sys, time, glob, parfive

# ===== MODO NÃO-INTERATIVO (Docker) =====
NON_INTERACTIVE = os.getenv("NON_INTERACTIVE", "0") == "1"

def ask(prompt, default="y"):
    """Confirmação que auto-responde quando sem TTY ou NON_INTERACTIVE=1."""
    if NON_INTERACTIVE or not sys.stdin.isatty():
        print(f"{prompt} [{default}] (auto)")
        return default
    try:
        return input(prompt)
    except EOFError:
        return default

def wait_enter():
    """Ignora 'Pressione Enter' quando sem TTY / NON_INTERACTIVE."""
    if NON_INTERACTIVE or not sys.stdin.isatty():
        return
    try:
        input('Pressione Enter')
    except EOFError:
        pass
# ========================================

#url = 'http://200.152.38.155/CNPJ/dados_abertos_cnpj/2024-08/' #padrão a partir de agosto/2024
#url_dados_abertos = 'https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/'
#url_dados_abertos = 'http://200.152.38.155/CNPJ/dados_abertos_cnpj/'
url_dados_abertos = 'https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/'

if os.path.exists("/dados-publicos-zip"):
    pasta_zip = "/dados-publicos-zip"
    pasta_cnpj = "/dados-publicos"
else:
    pasta_zip = "../dados-publicos-zip"
    pasta_cnpj = "../dados-publicos"

def requisitos():
    # se pastas não existirem, cria automaticamente
    if not os.path.isdir(pasta_cnpj):
        os.mkdir(pasta_cnpj)
    if not os.path.isdir(pasta_zip):
        os.mkdir(pasta_zip)
        
    arquivos_existentes = list(glob.glob(pasta_cnpj +'/*.*')) + list(glob.glob(pasta_zip + '/*.*'))
    if len(arquivos_existentes):
        r = ask(
            'Deseja apagar os arquivos das pastas ' + pasta_cnpj + ' e ' + pasta_zip + '?\n'
            + '\n'.join(arquivos_existentes)
            + '\nATENÇÃO: SE FOR EXECUTAR APENAS ALGUMA PARTE DO PROGRAMA, NÃO SELECIONE ESTA OPÇÃO, APAGUE MANUALMENTE.'
            + ' \nNÃO SERÁ POSSÍVEL REVERTER!!!!\nDeseja prosseguir e apagar os arquivos (y/n)??',
            default="y"
        )
        if r and r.upper()=='Y':
            for arq in arquivos_existentes:
                print('Apagando arquivo ' + arq)
                os.remove(arq)
        else:
            print('Parando... Apague os arquivos ' + pasta_cnpj + ' e ' + pasta_zip +' e tente novamente')
            wait_enter()
            sys.exit(1)

requisitos()

print(time.asctime(), f'Início de {sys.argv[0]}:')

soup_pagina_dados_abertos = BeautifulSoup(requests.get(url_dados_abertos).text, features="lxml")
try:
    ultima_referencia = sorted([link.get('href') for link in soup_pagina_dados_abertos.find_all('a') if link.get('href').startswith('20')])[-1]
except Exception:
    print('Não encontrou pastas em ' + url_dados_abertos)
    wait_enter()
    sys.exit(1)

url = url_dados_abertos + ultima_referencia
soup = BeautifulSoup(requests.get(url).text, features="lxml")
lista = []
print('Relação de Arquivos em ' + url)
for link in soup.find_all('a'):
    if str(link.get('href')).endswith('.zip'):
        cam = link.get('href')
        if not cam.startswith('http'):
            print(url+cam)
            lista.append(url+cam)
        else:
            print(cam)
            lista.append(cam)

if __name__ == '__main__':
    resp = ask(f'Deseja baixar os arquivos acima para a pasta {pasta_zip} (y/n)?', default="y")
    if resp.lower() not in ('y','s'):
        sys.exit()

print(time.asctime(), 'Início do Download dos arquivos...')

if True:  # baixa usando parfive, download em paralelo
    headers = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Windows; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36", "Accept": "*/*"}
    downloader = parfive.Downloader(max_conn=5, max_splits=1, config=parfive.SessionConfig(headers=headers))
    for url in lista:
        downloader.enqueue_file(url, path=pasta_zip, filename=os.path.split(url)[1])
    downloader.download()
else:  # baixar sequencial, rotina antiga
    def bar_progress(current, total, width=80):
        if total>=2**20:
            tbytes='Megabytes'
            unidade = 2**20
        else:
            tbytes='kbytes'
            unidade = 2**10
        progress_message = f"Baixando: %d%% [%d / %d] {tbytes}" % (current / total * 100, current//unidade, total//unidade)
        sys.stdout.write("\r" + progress_message)
        sys.stdout.flush()
    for k, url in enumerate(lista):
        print('\n' + time.asctime() + f' - item {k}: ' + url)
        wget.download(url, out=os.path.join(pasta_zip, os.path.split(url)[1]), bar=bar_progress)

print('\n\n'+ time.asctime(), f' Finalizou {sys.argv[0]}!!!')
print(f"Baixou {len(glob.glob(os.path.join(pasta_zip,'*.zip')))} arquivos.")
if __name__ == '__main__':
    wait_enter()

# lista dos arquivos (até julho/2024)
'''
http://200.152.38.155/CNPJ/Cnaes.zip
http://200.152.38.155/CNPJ/Empresas0.zip
http://200.152.38.155/CNPJ/Empresas1.zip
http://200.152.38.155/CNPJ/Empresas2.zip
http://200.152.38.155/CNPJ/Empresas3.zip
http://200.152.38.155/CNPJ/Empresas4.zip
http://200.152.38.155/CNPJ/Empresas5.zip
http://200.152.38.155/CNPJ/Empresas6.zip
http://200.152.38.155/CNPJ/Empresas7.zip
http://200.152.38.155/CNPJ/Empresas8.zip
http://200.152.38.155/CNPJ/Empresas9.zip
http://200.152.38.155/CNPJ/Estabelecimentos0.zip
http://200.152.38.155/CNPJ/Estabelecimentos1.zip
http://200.152.38.155/CNPJ/Estabelecimentos2.zip
http://200.152.38.155/CNPJ/Estabelecimentos3.zip
http://200.152.38.155/CNPJ/Estabelecimentos4.zip
http://200.152.38.155/CNPJ/Estabelecimentos5.zip
http://200.152.38.155/CNPJ/Estabelecimentos6.zip
http://200.152.38.155/CNPJ/Estabelecimentos7.zip
http://200.152.38.155/CNPJ/Estabelecimentos8.zip
http://200.152.38.155/CNPJ/Estabelecimentos9.zip
http://200.152.38.155/CNPJ/Motivos.zip
http://200.152.38.155/CNPJ/Municipios.zip
http://200.152.38.155/CNPJ/Naturezas.zip
http://200.152.38.155/CNPJ/Paises.zip
http://200.152.38.155/CNPJ/Qualificacoes.zip
http://200.152.38.155/CNPJ/Simples.zip
http://200.152.38.155/CNPJ/Socios0.zip
http://200.152.38.155/CNPJ/Socios1.zip
http://200.152.38.155/CNPJ/Socios2.zip
http://200.152.38.155/CNPJ/Socios3.zip
http://200.152.38.155/CNPJ/Socios4.zip
http://200.152.38.155/CNPJ/Socios5.zip
http://200.152.38.155/CNPJ/Socios6.zip
http://200.152.38.155/CNPJ/Socios7.zip
http://200.152.38.155/CNPJ/Socios8.zip
http://200.152.38.155/CNPJ/Socios9.zip
'''
