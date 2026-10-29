# -*- coding: utf-8 -*-
"""Testa core/dados.py: filtro por mês/ano/unidade e as mensagens de
erro quando a planilha da diretoria não tem o formato esperado."""

import pytest
from openpyxl import Workbook

from core import dados as mod_dados
from conftest import filial_exemplo, COLUNAS_DADOS


def test_carrega_e_filtra_por_mes_ano_unidade(criar_workbook_dados):
    linhas = [
        filial_exemplo(Filial='SP1', Regiao='Sudeste', mes=8, ano=2026, unidade='Comércio'),
        filial_exemplo(Filial='SP2', Regiao='Sudeste', mes=8, ano=2026, unidade='Comércio',
                        Faturamento=50000, **{'custo-pecas-medio': 0, 'Consultas': 0}),
        filial_exemplo(Filial='BA1', Regiao='Nordeste', mes=8, ano=2026, unidade='Comércio'),
        filial_exemplo(Filial='SP1', Regiao='Sudeste', mes=7, ano=2026, unidade='Comércio'),  # mês errado
        filial_exemplo(Filial='SP1', Regiao='Sudeste', mes=8, ano=2026, unidade='Indústria'),  # unidade errada
        filial_exemplo(Filial='SP1', Regiao='Sudeste', mes=8, ano=2025, unidade='Comércio'),  # ano errado
    ]
    caminho = criar_workbook_dados('dados.xlsx', linhas)

    registros = mod_dados.carregar_dados_mensais(caminho, mes=8, ano=2026, unidade='Comércio')

    assert len(registros) == 3
    filiais = {r['Filial'] for r in registros}
    assert filiais == {'SP1', 'SP2', 'BA1'}
    sp2 = next(r for r in registros if r['Filial'] == 'SP2')
    assert sp2['Faturamento'] == 50000
    assert sp2['custo_pecas_medio'] == 0


def test_sem_registros_para_o_periodo_devolve_lista_vazia(criar_workbook_dados):
    linhas = [filial_exemplo(mes=1, ano=2020)]
    caminho = criar_workbook_dados('dados.xlsx', linhas)
    registros = mod_dados.carregar_dados_mensais(caminho, mes=8, ano=2026, unidade='Comércio')
    assert registros == []


def test_aba_inexistente_gera_erro_claro(criar_workbook_dados):
    caminho = criar_workbook_dados('dados.xlsx', [filial_exemplo()])
    with pytest.raises(mod_dados.ErroLeituraDados, match='Dados'):
        mod_dados.carregar_dados_mensais(caminho, mes=8, ano=2026, aba='OutraAba')


def test_coluna_obrigatoria_ausente_gera_erro_claro(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Dados'
    colunas_incompletas = [c for c in COLUNAS_DADOS if c != 'PMR']
    ws.append(colunas_incompletas)
    ws.append([1] * len(colunas_incompletas))
    caminho = tmp_path / 'dados_incompletos.xlsx'
    wb.save(caminho)

    with pytest.raises(mod_dados.ErroLeituraDados, match='PMR'):
        mod_dados.carregar_dados_mensais(str(caminho), mes=8, ano=2026)


def test_coluna_mes_ausente_gera_erro_claro_em_vez_de_lista_vazia(tmp_path):
    """Antes da correção, se a aba não tivesse a coluna 'mes', o filtro
    simplesmente não batia com nada e o usuário só via 'sem dados' — sem
    nenhuma pista do motivo real."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Dados'
    colunas_sem_mes = [c for c in COLUNAS_DADOS if c != 'mes']
    ws.append(colunas_sem_mes)
    caminho = tmp_path / 'dados_sem_mes.xlsx'
    wb.save(caminho)

    with pytest.raises(mod_dados.ErroLeituraDados, match='mes'):
        mod_dados.carregar_dados_mensais(str(caminho), mes=8, ano=2026)


def test_arquivo_inexistente_gera_erro_claro():
    with pytest.raises(mod_dados.ErroLeituraDados):
        mod_dados.carregar_dados_mensais('caminho/que/nao/existe.xlsx', mes=8, ano=2026)


def test_listar_meses_disponiveis(criar_workbook_dados):
    linhas = [
        filial_exemplo(mes=8, ano=2026, unidade='Comércio'),
        filial_exemplo(mes=7, ano=2026, unidade='Comércio'),
        filial_exemplo(mes=8, ano=2025, unidade='Comércio'),
        filial_exemplo(mes=1, ano=2026, unidade='Indústria'),  # unidade diferente, não conta
    ]
    caminho = criar_workbook_dados('dados.xlsx', linhas)
    meses = mod_dados.listar_meses_disponiveis(caminho, unidade='Comércio')
    assert meses == [(2026, 8), (2026, 7), (2025, 8)]
