# -*- coding: utf-8 -*-
"""Trava as fórmulas de core/metricas.py com valores calculados à mão,
inclusive os casos-limite (custo/faturamento/consultas zerados, lucro
negativo) — qualquer mudança futura nessas fórmulas que altere um
resultado precisa passar por aqui conscientemente."""

import pytest

from core.metricas import calcular_metricas, somar_metricas, preencher_lucro_tot


def _registro(**overrides):
    base = {
        'Filial': 'SP1', 'Regiao': 'Sudeste',
        'Faturamento': 100000, 'vlr_servico': 20000, 'valor_pecas': 80000,
        'custo_pecas_medio': 60000, 'despesa_total': 15000, 'cst_estoque': 5000,
        'Consultas': 200, 'estoque': 30000, 'PMR': 25,
        'vlr_recebido': 90000, 'vlr_avencer': 8000, 'vlr_lp': 2000, 'lp_mes': 500,
        'vlr_atrasado': 1000, 'vlr_lp_recebido': 300, 'desp_flex': 2000,
    }
    base.update(overrides)
    return base


def test_calcular_metricas_caso_normal():
    m = calcular_metricas(_registro())
    assert m['Vlr Faturamento'] == 100000
    assert m['Vlr Serviço'] == 20000
    assert m['Vlr Produtos'] == 80000
    assert m['Custo Peças'] == 60000
    assert m['%Margem'] == pytest.approx((100000 - 60000) / 60000)
    assert m['%Fat'] == pytest.approx((100000 - 2000) / 100000)
    assert m['Flex'] == 2000
    assert m['Vlr Despesa'] == 15000
    assert m['%Despesa'] == pytest.approx(15000 / 100000)
    assert m['Manut Estq'] == 5000
    assert m['Vlr Consultas'] == 200
    assert m['%Consultas Fat.'] == pytest.approx(100000 / 200)
    lucro_esperado = 100000 - 60000 - 15000 + 300
    assert m['Vlr Lucro S/IRRF'] == lucro_esperado
    assert m['%Lucro'] == pytest.approx(lucro_esperado / 100000)
    assert m['%Lucro Tot'] is None  # preenchido depois, por core.relatorios
    assert m['Estoque/Mês'] == 30000
    assert m['PMR'] == 25
    assert m['Vlr Recebido'] == 90000
    assert m['Vlr a Vencer'] == 8000
    assert m['LP /Total'] == 2000
    assert m['LP Mês'] == 500
    assert m['Inadimplência'] == 1000
    assert m['% Inad/Vencer'] == pytest.approx(1000 / 9000)
    assert m['Recup. Cart'] == 300


def test_calcular_metricas_custo_zero_nao_divide_por_zero():
    m = calcular_metricas(_registro(custo_pecas_medio=0))
    assert m['%Margem'] == 0.0


def test_calcular_metricas_faturamento_zero_nao_divide_por_zero():
    m = calcular_metricas(_registro(Faturamento=0))
    assert m['%Fat'] == 0.0
    assert m['%Despesa'] == 0.0
    assert m['%Lucro'] == 0.0


def test_calcular_metricas_consultas_zero_nao_divide_por_zero():
    m = calcular_metricas(_registro(Consultas=0))
    assert m['%Consultas Fat.'] == 0.0


def test_calcular_metricas_sem_avencer_nem_atrasado_nao_divide_por_zero():
    m = calcular_metricas(_registro(vlr_avencer=0, vlr_atrasado=0))
    assert m['% Inad/Vencer'] == 0.0


def test_calcular_metricas_lucro_negativo():
    m = calcular_metricas(_registro(Faturamento=30000, custo_pecas_medio=20000,
                                     despesa_total=15000, vlr_lp_recebido=0))
    assert m['Vlr Lucro S/IRRF'] == 30000 - 20000 - 15000
    assert m['Vlr Lucro S/IRRF'] < 0
    assert m['%Lucro'] == pytest.approx(-5000 / 30000)


def test_calcular_metricas_campos_ausentes_viram_zero():
    m = calcular_metricas({'Filial': 'X', 'Regiao': 'Y'})
    assert m['Vlr Faturamento'] == 0
    assert m['%Margem'] == 0.0
    assert m['Vlr Lucro S/IRRF'] == 0


def test_somar_metricas_soma_moeda_e_recalcula_percentual():
    m1 = calcular_metricas(_registro(Filial='SP1'))
    m2 = calcular_metricas(_registro(Filial='SP2', Faturamento=50000, custo_pecas_medio=30000,
                                      despesa_total=5000, desp_flex=0, vlr_lp_recebido=0,
                                      vlr_avencer=4000, vlr_atrasado=500, Consultas=100))
    total = somar_metricas([m1, m2])

    assert total['Vlr Faturamento'] == 100000 + 50000
    assert total['Custo Peças'] == 60000 + 30000
    assert total['Vlr Despesa'] == 15000 + 5000
    # PMR é média simples, não soma
    assert total['PMR'] == pytest.approx((25 + 25) / 2)

    fat = total['Vlr Faturamento']
    custo = total['Custo Peças']
    despesa = total['Vlr Despesa']
    lucro = total['Vlr Lucro S/IRRF']
    assert total['%Margem'] == pytest.approx((fat - custo) / custo)
    assert total['%Despesa'] == pytest.approx(despesa / fat)
    assert total['%Lucro'] == pytest.approx(lucro / fat)


def test_somar_metricas_lista_vazia():
    total = somar_metricas([])
    assert total['Vlr Faturamento'] == 0
    assert total['%Margem'] == 0.0
    assert total['PMR'] == 0


def test_preencher_lucro_tot_participacao_no_grupo():
    m1 = calcular_metricas(_registro(Filial='SP1'))  # lucro = 25300
    m2 = calcular_metricas(_registro(Filial='SP2', Faturamento=25300))  # lucro = 25300-60000-15000+300 (negativo)
    lista = [m1, m2]
    lucro_total = sum(m['Vlr Lucro S/IRRF'] for m in lista)
    preencher_lucro_tot(lista, lucro_total)
    assert m1['%Lucro Tot'] == pytest.approx(m1['Vlr Lucro S/IRRF'] / lucro_total)
    assert m2['%Lucro Tot'] == pytest.approx(m2['Vlr Lucro S/IRRF'] / lucro_total)


def test_preencher_lucro_tot_grupo_com_lucro_total_zero():
    m1 = calcular_metricas(_registro(Faturamento=0, custo_pecas_medio=0, despesa_total=0,
                                      vlr_lp_recebido=0))
    preencher_lucro_tot([m1], 0)
    assert m1['%Lucro Tot'] == 0.0
