# -*- coding: utf-8 -*-
"""
core/appdir.py

Descobre a pasta "raiz" do programa, funcionando tanto quando ele roda
como script Python normal (python main.py) quanto quando roda como um
.exe gerado pelo PyInstaller.

Isso importa porque, dentro de um .exe gerado com --onefile, o
PyInstaller extrai os arquivos para uma pasta temporária a cada
execução (e apaga tudo ao fechar) — se o programa salvasse o cadastro
de e-mails ou o mapeamento de metas nessa pasta temporária, tudo seria
perdido toda vez que o programa fosse fechado. Por isso os dados
persistentes (pasta "data/") sempre ficam ao lado do .exe (ou do
main.py), nunca dentro da pasta temporária do PyInstaller.
"""

import os
import shutil
import sys

# Nome da pasta onde ficam os arquivos internos do programa (cadastros,
# configurações, log de erro) — deliberadamente descritivo em português,
# pra ficar claro pra quem não é técnico que não precisa mexer aqui.
NOME_PASTA_DADOS = 'Arquivos do Programa (não mexer)'


def base_dir():
    """Pasta onde o programa deve ler/gravar dados persistentes
    (cadastros, configurações, relatórios gerados)."""
    if getattr(sys, 'frozen', False):
        # Rodando como .exe (PyInstaller) -> pasta onde está o .exe
        return os.path.dirname(sys.executable)
    # Rodando como script normal -> pasta raiz do projeto (uma acima de core/)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bootstrap_dados_iniciais():
    """No primeiro uso do .exe (quando ainda não existe uma pasta data/ ao
    lado do executável), copia pra lá os arquivos de modelo/referência que
    foram empacotados dentro do .exe (--add-data "data;data"), como o
    modelo de exemplo de metas. Sem efeito quando roda como script normal
    (nesse caso a pasta data/ do próprio projeto já existe)."""
    if not getattr(sys, 'frozen', False):
        return
    destino = os.path.join(base_dir(), NOME_PASTA_DADOS)
    if os.path.isdir(destino):
        return
    origem = os.path.join(getattr(sys, '_MEIPASS', ''), 'data', 'metas_modelo_exemplo.xlsx')
    os.makedirs(destino, exist_ok=True)
    if os.path.isfile(origem):
        shutil.copy2(origem, os.path.join(destino, 'metas_modelo_exemplo.xlsx'))
