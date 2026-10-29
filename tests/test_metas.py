# -*- coding: utf-8 -*-
"""Testa core/metas.py: leitura de cabeçalhos, round-trip do mapeamento
salvo em disco, e a montagem final de {filial: {metrica: meta}}."""

import pytest
from openpyxl import Workbook

from core import metas as mod_metas


def _criar_planilha_metas(tmp_path, linhas, cabecalho=None):
    cabecalho = cabecalho or ['Loja', 'Meta Fat.', 'Meta Margem', 'Meta PMR']
    wb = Workbook()
    ws = wb.active
    ws.title = 'Metas'
    ws.append(cabecalho)
    for linha in linhas:
        ws.append(linha)
    caminho = tmp_path / 'metas.xlsx'
    wb.save(caminho)
    return str(caminho)


def test_ler_cabecalhos(tmp_path):
    caminho = _criar_planilha_metas(tmp_path, [['SP1', 100000, 0.3, 20]])
    cabecalhos = mod_metas.ler_cabecalhos(caminho, 'Metas')
    assert cabecalhos == ['Loja', 'Meta Fat.', 'Meta Margem', 'Meta PMR']


def test_listar_abas(tmp_path):
    caminho = _criar_planilha_metas(tmp_path, [])
    assert mod_metas.listar_abas(caminho) == ['Metas']


def test_salvar_e_carregar_mapeamento_roundtrip(redirecionar_dados):
    mapeamento = {'coluna_filial': 'Loja', 'Vlr Faturamento': 'Meta Fat.', '%Margem': 'Meta Margem'}
    mod_metas.salvar_mapeamento('C:/algum/arquivo.xlsx', 'Metas', mapeamento)

    cfg = mod_metas.carregar_config_mapeamento()
    assert cfg is not None
    assert cfg['caminho_arquivo'] == 'C:/algum/arquivo.xlsx'
    assert cfg['aba'] == 'Metas'
    assert cfg['mapeamento'] == mapeamento


def test_carregar_config_mapeamento_sem_arquivo_devolve_none(redirecionar_dados):
    assert mod_metas.carregar_config_mapeamento() is None


def test_carregar_metas_monta_dict_por_filial(tmp_path):
    caminho = _criar_planilha_metas(tmp_path, [
        ['SP1', 100000, 0.3, 20],
        ['SP2', 50000, None, 15],  # meta de margem em branco pra essa filial
    ])
    mapeamento = {'coluna_filial': 'Loja', 'Vlr Faturamento': 'Meta Fat.',
                  '%Margem': 'Meta Margem', 'PMR': 'Meta PMR'}

    metas = mod_metas.carregar_metas(caminho, 'Metas', mapeamento)

    assert metas['SP1'] == {'Vlr Faturamento': 100000, '%Margem': 0.3, 'PMR': 20}
    assert metas['SP2'] == {'Vlr Faturamento': 50000, 'PMR': 15}  # sem %Margem


def test_carregar_metas_ignora_metrica_nao_mapeada(tmp_path):
    caminho = _criar_planilha_metas(tmp_path, [['SP1', 100000, 0.3, 20]])
    mapeamento = {'coluna_filial': 'Loja', 'Vlr Faturamento': 'Meta Fat.'}  # só uma métrica mapeada

    metas = mod_metas.carregar_metas(caminho, 'Metas', mapeamento)

    assert metas['SP1'] == {'Vlr Faturamento': 100000}


def test_carregar_metas_sem_coluna_filial_valida_gera_erro(tmp_path):
    caminho = _criar_planilha_metas(tmp_path, [['SP1', 100000, 0.3, 20]])
    mapeamento = {'Vlr Faturamento': 'Meta Fat.'}  # sem 'coluna_filial'
    with pytest.raises(mod_metas.ErroMetas):
        mod_metas.carregar_metas(caminho, 'Metas', mapeamento)

    mapeamento_invalido = {'coluna_filial': 'ColunaQueNaoExiste'}
    with pytest.raises(mod_metas.ErroMetas):
        mod_metas.carregar_metas(caminho, 'Metas', mapeamento_invalido)


def test_carregar_metas_pula_linhas_sem_filial(tmp_path):
    caminho = _criar_planilha_metas(tmp_path, [
        ['SP1', 100000, 0.3, 20],
        [None, 999999, 0.9, 1],  # linha sem filial, deve ser ignorada
    ])
    mapeamento = {'coluna_filial': 'Loja', 'Vlr Faturamento': 'Meta Fat.'}
    metas = mod_metas.carregar_metas(caminho, 'Metas', mapeamento)
    assert list(metas.keys()) == ['SP1']
