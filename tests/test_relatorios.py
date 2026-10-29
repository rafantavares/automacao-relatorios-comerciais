# -*- coding: utf-8 -*-
"""Testa core/relatorios.py: a decisão de cor é feita por funções puras
(_cor_por_meta_tag / _cor_padrao_tag), testadas diretamente sem precisar
renderizar PDF nenhum. A geração de PDF em si é testada gerando arquivos
de verdade em tmp_path e reabrindo com pypdf, conferindo (via texto
extraído, com espaços/quebras de linha normalizados) que os rótulos e
valores certos aparecem."""

import os
import re

import pytest
from pypdf import PdfReader

from core.relatorios import (
    _cor_por_meta_tag, _cor_padrao_tag, _agregar,
    gerar_relatorio_regiao, gerar_relatorio_filial, gerar_dashboard_geral,
    gerar_todos_relatorios, carregar_relatorios_gerados,
)
from conftest import filial_exemplo


def _para_registro_core(dados_filial):
    """Converte um dict no formato "coluna da planilha" (conftest.filial_exemplo)
    pro formato de chave interna que core.metricas espera."""
    mapa = {
        'Filial': 'Filial', 'Regiao': 'Regiao', 'Faturamento': 'Faturamento',
        'vlr-servico': 'vlr_servico', 'valor-pecas': 'valor_pecas',
        'custo-pecas-medio': 'custo_pecas_medio', 'despesa-total': 'despesa_total',
        'cst-estoque': 'cst_estoque', 'Consultas': 'Consultas', 'estoque': 'estoque',
        'PMR': 'PMR', 'vlr-recebido': 'vlr_recebido', 'vlr-avencer': 'vlr_avencer',
        'vlr-lp': 'vlr_lp', 'lp-mes': 'lp_mes', 'vlr-atrasado': 'vlr_atrasado',
        'vlr-lp-recebido': 'vlr_lp_recebido', 'desp-flex': 'desp_flex',
    }
    return {chave_interna: dados_filial[chave_planilha] for chave_planilha, chave_interna in mapa.items()}


def _texto_pdf(caminho):
    """Texto de todas as páginas do PDF, com espaços/quebras de linha
    removidos — o reportlab quebra números em várias linhas quando a
    coluna é estreita (ex: "100,000.0" + "\\n0"), e remover os espaços
    reconstrói o valor original sem alterar os dígitos."""
    leitor = PdfReader(caminho)
    texto = "\n".join(pagina.extract_text() for pagina in leitor.pages)
    return re.sub(r'\s+', '', texto)


def _contem(caminho, *trechos):
    texto = _texto_pdf(caminho)
    return all(re.sub(r'\s+', '', t) in texto for t in trechos)


# --------------------------------------------------- Decisão de cor (puro)
def test_cor_por_meta_sem_meta_devolve_none():
    assert _cor_por_meta_tag(1000, None, 'Vlr Faturamento') is None
    assert _cor_por_meta_tag(1000, 0, 'Vlr Faturamento') is None


def test_cor_por_meta_metrica_maior_melhor():
    assert _cor_por_meta_tag(100, 80, 'Vlr Faturamento') == 'verde'      # passou da meta
    assert _cor_por_meta_tag(95, 100, 'Vlr Faturamento') == 'amarelo'    # 95% da meta
    assert _cor_por_meta_tag(50, 100, 'Vlr Faturamento') == 'vermelho'   # bem abaixo


def test_cor_por_meta_metrica_menor_melhor():
    assert _cor_por_meta_tag(0.15, 0.20, '%Despesa') == 'verde'      # gastou menos que a meta
    assert _cor_por_meta_tag(0.22, 0.20, '%Despesa') == 'amarelo'    # levemente acima
    assert _cor_por_meta_tag(0.40, 0.20, '%Despesa') == 'vermelho'   # bem acima


def test_cor_padrao_lucro_por_sinal():
    assert _cor_padrao_tag('Vlr Lucro S/IRRF', 500) == 'verde'
    assert _cor_padrao_tag('Vlr Lucro S/IRRF', -500) == 'vermelho'
    assert _cor_padrao_tag('Vlr Lucro S/IRRF', 0) is None


def test_cor_padrao_inadimplencia_por_limiar():
    assert _cor_padrao_tag('% Inad/Vencer', 0.11) == 'vermelho'
    assert _cor_padrao_tag('% Inad/Vencer', 0.05) == 'verde'


def test_cor_padrao_coluna_sem_regra_devolve_none():
    assert _cor_padrao_tag('Vlr Faturamento', 1000) is None


# --------------------------------------------------------- Geração de PDF
def test_gerar_relatorio_regiao_valores_e_subtotal(tmp_path):
    sp1 = _para_registro_core(filial_exemplo(Filial='SP1', Regiao='Sudeste', Faturamento=100000,
                                              **{'custo-pecas-medio': 60000}))
    sp2 = _para_registro_core(filial_exemplo(Filial='SP2', Regiao='Sudeste', Faturamento=50000,
                                              **{'custo-pecas-medio': 30000, 'despesa-total': 5000}))
    metricas_por_filial, _por_regiao, subtotal_por_regiao, _total_geral = _agregar([sp1, sp2])

    caminho = gerar_relatorio_regiao('Sudeste', subtotal_por_regiao['Sudeste'], metricas_por_filial,
                                      {}, str(tmp_path))

    assert os.path.exists(caminho)
    assert os.path.basename(os.path.dirname(caminho)) == 'Sudeste'  # subpasta por região
    assert _contem(caminho, 'Sudeste', 'SP1', 'SP2', '150,000.00')  # soma dos 2 faturamentos


def test_gerar_relatorio_filial_tem_3_linhas_com_dados_diferentes(tmp_path):
    """Corrige o bug em que Região/Filial/Total Geral mostravam sempre a
    mesma linha (a da própria filial). Agora cada linha reflete o
    escopo certo: a filial sozinha, o subtotal real da região, e o total
    de toda a empresa — três números diferentes."""
    sp1 = _para_registro_core(filial_exemplo(Filial='SP1', Regiao='Sudeste', Faturamento=100000,
                                              **{'custo-pecas-medio': 60000}))
    sp2 = _para_registro_core(filial_exemplo(Filial='SP2', Regiao='Sudeste', Faturamento=50000,
                                              **{'custo-pecas-medio': 30000, 'despesa-total': 5000}))
    ba1 = _para_registro_core(filial_exemplo(Filial='BA1', Regiao='Nordeste', Faturamento=30000,
                                              **{'custo-pecas-medio': 20000, 'despesa-total': 5000}))
    metricas_por_filial, _por_regiao, subtotal_por_regiao, total_geral = _agregar([sp1, sp2, ba1])

    caminho = gerar_relatorio_filial('Sudeste', 'SP1', metricas_por_filial['SP1'],
                                      subtotal_por_regiao['Sudeste'], total_geral, {}, str(tmp_path))

    # Faturamento: SP1 sozinha = 100.000; região Sudeste (SP1+SP2) = 150.000;
    # total geral da empresa (Sudeste+Nordeste) = 180.000.
    assert _contem(caminho, 'Sudeste', 'SP1', 'Total Geral')
    texto = _texto_pdf(caminho)
    assert '100,000.00' in texto  # linha da Filial
    assert '150,000.00' in texto  # linha da Região (subtotal real, não repete a filial)
    assert '180,000.00' in texto  # linha Total Geral (soma de toda a empresa)


def test_relatorio_filial_com_meta_inclui_tabela_comparativo(tmp_path):
    sp1 = _para_registro_core(filial_exemplo(Filial='SP1', Regiao='Sudeste', Faturamento=100000))
    metricas_por_filial, _por_regiao, subtotal_por_regiao, total_geral = _agregar([sp1])
    metas = {'SP1': {'Vlr Faturamento': 80000}}  # meta menor que o real -> bateu

    caminho = gerar_relatorio_filial('Sudeste', 'SP1', metricas_por_filial['SP1'],
                                      subtotal_por_regiao['Sudeste'], total_geral, metas, str(tmp_path))

    assert _contem(caminho, 'Comparativo com a meta', 'Vlr Faturamento', '80,000.00')


def test_gerar_dashboard_geral_cria_arquivo_com_resumo(tmp_path):
    sp1 = _para_registro_core(filial_exemplo(Filial='SP1', Regiao='Sudeste'))
    ba1 = _para_registro_core(filial_exemplo(Filial='BA1', Regiao='Nordeste', Faturamento=30000,
                                              **{'custo-pecas-medio': 20000, 'despesa-total': 5000}))
    metricas_por_filial, _por_regiao, subtotal_por_regiao, total_geral = _agregar([sp1, ba1])

    caminho = gerar_dashboard_geral(metricas_por_filial, subtotal_por_regiao, total_geral, str(tmp_path))

    assert os.path.exists(caminho)
    assert os.path.basename(caminho) == '00_Dashboard_Geral.pdf'
    assert _contem(caminho, 'Panorama Geral', 'Total Geral', 'Sudeste', 'Nordeste')
    assert os.path.getsize(caminho) > 20_000  # tem gráficos embutidos, não só texto/tabela


def test_dashboard_com_muitas_filiais_nao_estoura_a_pagina(tmp_path):
    """Bug encontrado na inspeção visual: com dezenas de filiais, o
    gráfico horizontal de %Lucro crescia mais alto que uma página inteira
    e o reportlab quebrava a geração (LayoutError, imagem não cabia em
    nenhuma página). A altura precisa ser limitada, ficando mais
    compacto em vez de estourar."""
    registros = [
        _para_registro_core(filial_exemplo(Filial=f'F{i:02d}', Regiao='Sudeste', Faturamento=10000 + i))
        for i in range(60)
    ]
    metricas_por_filial, _por_regiao, subtotal_por_regiao, total_geral = _agregar(registros)

    # não pode levantar reportlab.platypus.doctemplate.LayoutError
    caminho = gerar_dashboard_geral(metricas_por_filial, subtotal_por_regiao, total_geral, str(tmp_path))

    assert os.path.exists(caminho)
    reader = PdfReader(caminho)
    assert len(reader.pages) >= 2  # tabela+gráficos por região numa página, %lucro por filial em outra


def test_dashboard_lucro_tot_e_participacao_da_regiao_no_total_nao_100_por_cento(tmp_path):
    """Bug encontrado na inspeção visual: a tabela do dashboard reusava o
    subtotal da região (onde '%Lucro Tot' vale 100%, por representar a
    região em relação a si mesma) direto ao lado de outras regiões — toda
    linha aparecia com 100.00%. Precisa mostrar a participação real de
    cada região no lucro total da empresa; só a linha Total Geral é 100%."""
    sp1 = _para_registro_core(filial_exemplo(Filial='SP1', Regiao='Sudeste', Faturamento=100000,
                                              **{'custo-pecas-medio': 60000}))
    ba1 = _para_registro_core(filial_exemplo(Filial='BA1', Regiao='Nordeste', Faturamento=30000,
                                              **{'custo-pecas-medio': 20000, 'despesa-total': 5000}))
    metricas_por_filial, _por_regiao, subtotal_por_regiao, total_geral = _agregar([sp1, ba1])

    caminho = gerar_dashboard_geral(metricas_por_filial, subtotal_por_regiao, total_geral, str(tmp_path))
    texto = _texto_pdf(caminho)

    lucro_sudeste = subtotal_por_regiao['Sudeste']['Vlr Lucro S/IRRF']
    lucro_total = total_geral['Vlr Lucro S/IRRF']
    participacao_esperada = f"{(lucro_sudeste / lucro_total) * 100:,.2f}%"
    assert participacao_esperada != "100.00%"
    assert participacao_esperada in texto
    # a região não pode aparecer com 100.00% (só o Total Geral pode)
    assert texto.count("100.00%") == 1


def test_gerar_todos_relatorios_agrupa_por_regiao_em_subpastas(tmp_path):
    registros = [
        _para_registro_core(filial_exemplo(Filial='SP1', Regiao='Sudeste')),
        _para_registro_core(filial_exemplo(Filial='SP2', Regiao='Sudeste', Faturamento=50000)),
        _para_registro_core(filial_exemplo(Filial='BA1', Regiao='Nordeste', Faturamento=30000)),
    ]
    gerados = gerar_todos_relatorios(registros, {}, str(tmp_path))

    tipos_regiao = [g for g in gerados if g['tipo'] == 'regiao']
    tipos_filial = [g for g in gerados if g['tipo'] == 'filial']
    tipos_dashboard = [g for g in gerados if g['tipo'] == 'dashboard']
    assert {g['regiao'] for g in tipos_regiao} == {'Sudeste', 'Nordeste'}
    assert {g['filial'] for g in tipos_filial} == {'SP1', 'SP2', 'BA1'}
    assert len(tipos_dashboard) == 1
    for item in gerados:
        assert os.path.exists(item['caminho'])

    # cada arquivo de região/filial fica dentro de uma subpasta com o nome da região
    for item in tipos_regiao + tipos_filial:
        assert os.path.basename(os.path.dirname(item['caminho'])) == item['regiao']

    # o dashboard fica solto na raiz da pasta de saída, não numa subpasta
    assert os.path.dirname(tipos_dashboard[0]['caminho']) == str(tmp_path)
    assert os.path.basename(tipos_dashboard[0]['caminho']) == '00_Dashboard_Geral.pdf'


def test_carregar_relatorios_gerados_recupera_uma_pasta_ja_gerada(tmp_path):
    """Fechar e reabrir o programa não pode perder a referência aos
    relatórios de um mês já gerado — gerar_todos_relatorios salva um
    manifesto na própria pasta, e carregar_relatorios_gerados o lê de
    volta, reconstruindo a mesma lista."""
    registros = [
        _para_registro_core(filial_exemplo(Filial='SP1', Regiao='Sudeste')),
        _para_registro_core(filial_exemplo(Filial='BA1', Regiao='Nordeste', Faturamento=30000)),
    ]
    gerados = gerar_todos_relatorios(registros, {}, str(tmp_path))

    recarregados = carregar_relatorios_gerados(str(tmp_path))

    chave = lambda g: (g['tipo'], g['regiao'], g['filial'], g['caminho'])
    assert sorted(gerados, key=chave) == sorted(recarregados, key=chave)


def test_carregar_relatorios_gerados_ignora_arquivo_apagado_a_mao(tmp_path):
    registros = [_para_registro_core(filial_exemplo(Filial='SP1', Regiao='Sudeste'))]
    gerados = gerar_todos_relatorios(registros, {}, str(tmp_path))
    item_filial = next(g for g in gerados if g['tipo'] == 'filial')
    os.remove(item_filial['caminho'])

    recarregados = carregar_relatorios_gerados(str(tmp_path))

    assert len(recarregados) == len(gerados) - 1
    assert not any(g['tipo'] == 'filial' for g in recarregados)


def test_carregar_relatorios_gerados_pasta_sem_manifesto_levanta_erro(tmp_path):
    (tmp_path / 'algum_arquivo.txt').write_text('nada a ver')
    with pytest.raises(FileNotFoundError):
        carregar_relatorios_gerados(str(tmp_path))
