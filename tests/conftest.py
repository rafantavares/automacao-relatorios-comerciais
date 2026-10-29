# -*- coding: utf-8 -*-
"""
tests/conftest.py

Fixtures compartilhadas pelos testes:
- `redirecionar_dados`: garante que nenhum teste lê/grava nos arquivos
  reais em data/ do projeto (config.json, metas_mapeamento.json,
  emails_gerentes.csv) — tudo aponta pra uma pasta temporária isolada.
- `criar_workbook_dados`: monta um .xlsx sintético no formato que
  core/dados.py espera (aba "Dados"), pra testar sem depender de um
  arquivo real da diretoria.
"""

import os
import sys

import pytest
from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as mod_config
from core import metas as mod_metas

COLUNAS_DADOS = [
    'Filial', 'Regiao', 'Faturamento', 'vlr-servico', 'valor-pecas',
    'custo-pecas-medio', 'despesa-total', 'cst-estoque', 'Consultas',
    'estoque', 'PMR', 'vlr-recebido', 'vlr-avencer', 'vlr-lp', 'lp-mes',
    'vlr-atrasado', 'vlr-lp-recebido', 'desp-flex', 'mes', 'ano', 'unidade',
]


@pytest.fixture
def redirecionar_dados(tmp_path, monkeypatch):
    """Redireciona todos os caminhos persistentes do core/ pra uma pasta
    temporária, isolando o teste dos dados reais do projeto — inclusive
    a pasta de saída PADRÃO dos relatórios. Sem essa última parte, um
    teste que chama `_gerar_relatorios()` sem escolher uma pasta
    explicitamente (via `app.var_pasta_saida.set(...)`) cairia no valor
    padrão real (`mod_config.PADRAO['pasta_saida']`, que aponta pra
    output/ dentro do próprio projeto) e escreveria PDFs de teste ali —
    exatamente o bug que gerou a pasta de teste 'output/08-ago-2026' na
    pasta real do projeto antes desse fixture existir."""
    monkeypatch.setattr(mod_config, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(mod_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    monkeypatch.setattr(mod_config, 'PADRAO', {**mod_config.PADRAO, 'pasta_saida': str(tmp_path / 'output')})
    monkeypatch.setattr(mod_metas, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(mod_metas, 'MAPEAMENTO_PATH', str(tmp_path / 'metas_mapeamento.json'))
    monkeypatch.setattr(mod_metas, 'METAS_CACHE_PATH', str(tmp_path / 'metas_ultimo_arquivo.json'))
    return tmp_path


@pytest.fixture
def criar_workbook_dados(tmp_path):
    """Devolve uma função que monta um .xlsx sintético de dados mensais
    (aba "Dados") a partir de uma lista de dicts com as colunas de
    COLUNAS_DADOS, e devolve o caminho do arquivo criado."""

    def _criar(nome_arquivo, linhas, aba='Dados'):
        wb = Workbook()
        ws = wb.active
        ws.title = aba
        ws.append(COLUNAS_DADOS)
        for linha in linhas:
            ws.append([linha.get(c) for c in COLUNAS_DADOS])
        caminho = tmp_path / nome_arquivo
        wb.save(caminho)
        return str(caminho)

    return _criar


def filial_exemplo(**overrides):
    """Uma linha de dados "razoável" de filial, com valores que dão pra
    conferir à mão — usada como base em vários testes; passe overrides
    pra mudar só os campos que importam pro teste."""
    base = {
        'Filial': 'SP1', 'Regiao': 'Sudeste',
        'Faturamento': 100000, 'vlr-servico': 20000, 'valor-pecas': 80000,
        'custo-pecas-medio': 60000, 'despesa-total': 15000, 'cst-estoque': 5000,
        'Consultas': 200, 'estoque': 30000, 'PMR': 25,
        'vlr-recebido': 90000, 'vlr-avencer': 8000, 'vlr-lp': 2000, 'lp-mes': 500,
        'vlr-atrasado': 1000, 'vlr-lp-recebido': 300, 'desp-flex': 2000,
        'mes': 8, 'ano': 2026, 'unidade': 'Comércio',
    }
    base.update(overrides)
    return base
