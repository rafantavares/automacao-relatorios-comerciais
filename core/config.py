# -*- coding: utf-8 -*-
"""
core/config.py

Guarda as configurações do programa (caminho do último arquivo de dados
usado, credenciais de e-mail, etc.) em data/config.json, no próprio
notebook. Nada disso é enviado pra lugar nenhum.

ATENÇÃO: a senha de app do Gmail fica salva em texto simples nesse
arquivo, pra não precisar digitar toda vez. Proteja o acesso a essa
pasta como faria com qualquer outro arquivo sensível do computador, e
use sempre uma SENHA DE APP do Gmail (revogável a qualquer momento),
nunca a senha principal da conta.
"""

import json
import os

from .appdir import base_dir, NOME_PASTA_DADOS

DATA_DIR = os.path.join(base_dir(), NOME_PASTA_DADOS)
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')

PADRAO = {
    'gmail_remetente': '',
    'gmail_senha_app': '',
    'ultimo_arquivo_dados': '',
    'pasta_saida': os.path.join(base_dir(), 'Relatórios'),
    # Pares [Regiao, Filial] vistos na última geração de relatórios bem
    # sucedida — usado pra popular o dropdown de Região/Filial na aba de
    # e-mails dos gerentes, mesmo antes de gerar relatórios de novo numa
    # sessão nova.
    'regioes_filiais': [],
}


def carregar():
    if not os.path.exists(CONFIG_PATH):
        return dict(PADRAO)
    with open(CONFIG_PATH, encoding='utf-8') as f:
        dados = json.load(f)
    config = dict(PADRAO)
    config.update(dados)
    return config


def salvar(config):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
