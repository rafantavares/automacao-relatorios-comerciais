# -*- coding: utf-8 -*-
"""
core/metricas.py

Calcula, a partir dos campos brutos de uma filial (vindos de core.dados),
as mesmas métricas usadas no relatório "Resultado Comércio Mensal" que a
diretoria já usa hoje (Vlr Faturamento, %Margem, %Lucro, etc.).

As fórmulas abaixo foram conferidas célula a célula contra um relatório
real da diretoria antes de este programa ser criado, então
os números batem exatamente com o que a diretoria já manda hoje.

ORDEM_COLUNAS define a ordem e os nomes de coluna usados nos relatórios
gerados — é a mesma ordem do relatório original em PDF.
"""

ORDEM_COLUNAS = [
    "Vlr Faturamento", "Vlr Serviço", "Vlr Produtos", "Custo Peças",
    "%Margem", "%Fat", "Flex", "Vlr Despesa", "%Despesa", "Manut Estq",
    "Vlr Consultas", "%Consultas Fat.", "Vlr Lucro S/IRRF", "%Lucro",
    "%Lucro Tot", "Estoque/Mês", "PMR", "Vlr Recebido", "Vlr a Vencer",
    "LP /Total", "LP Mês", "Inadimplência", "% Inad/Vencer", "Recup. Cart",
]

# Colunas que são valores monetários (formatação e comparação com metas)
COLUNAS_MOEDA = {
    "Vlr Faturamento", "Vlr Serviço", "Vlr Produtos", "Custo Peças", "Flex",
    "Vlr Despesa", "Manut Estq", "Vlr Consultas", "Vlr Lucro S/IRRF",
    "Estoque/Mês", "Vlr Recebido", "Vlr a Vencer", "LP /Total", "LP Mês",
    "Inadimplência", "Recup. Cart",
}
# Colunas que são percentuais
COLUNAS_PERCENTUAL = {"%Margem", "%Fat", "%Despesa", "%Consultas Fat.", "%Lucro",
                       "%Lucro Tot", "% Inad/Vencer"}


def calcular_metricas(d):
    """Recebe um registro bruto (dict, ver core.dados.RAW_FIELDS) e devolve
    um dict com as métricas do relatório, na mesma ordem/nomes de
    ORDEM_COLUNAS (exceto '%Lucro Tot', que depende do total do grupo e é
    preenchido depois por core.relatorios)."""

    fat = d.get('Faturamento') or 0
    custo = d.get('custo_pecas_medio') or 0
    despesa = d.get('despesa_total') or 0
    consultas = d.get('Consultas') or 0
    flex = d.get('desp_flex') or 0
    recup = d.get('vlr_lp_recebido') or 0
    atrasado = d.get('vlr_atrasado') or 0
    avencer = d.get('vlr_avencer') or 0

    margem = (fat - custo) / custo if custo else 0.0
    pfat = (fat - flex) / fat if fat else 0.0
    pdespesa = despesa / fat if fat else 0.0
    pconsultas = fat / consultas if consultas else 0.0
    lucro = fat - custo - despesa + recup
    plucro = lucro / fat if fat else 0.0
    pinad = atrasado / (avencer + atrasado) if (avencer + atrasado) else 0.0

    return {
        "Vlr Faturamento": fat,
        "Vlr Serviço": d.get('vlr_servico') or 0,
        "Vlr Produtos": d.get('valor_pecas') or 0,
        "Custo Peças": custo,
        "%Margem": margem,
        "%Fat": pfat,
        "Flex": flex,
        "Vlr Despesa": despesa,
        "%Despesa": pdespesa,
        "Manut Estq": d.get('cst_estoque') or 0,
        "Vlr Consultas": consultas,
        "%Consultas Fat.": pconsultas,
        "Vlr Lucro S/IRRF": lucro,
        "%Lucro": plucro,
        "%Lucro Tot": None,  # preenchido depois, em relação ao grupo (região/geral)
        "Estoque/Mês": d.get('estoque') or 0,
        "PMR": d.get('PMR') or 0,
        "Vlr Recebido": d.get('vlr_recebido') or 0,
        "Vlr a Vencer": avencer,
        "LP /Total": d.get('vlr_lp') or 0,
        "LP Mês": d.get('lp_mes') or 0,
        "Inadimplência": atrasado,
        "% Inad/Vencer": pinad,
        "Recup. Cart": recup,
    }


def somar_metricas(lista_metricas):
    """Soma um grupo de dicionários de métricas (ex: todas as filiais de uma
    região) para gerar a linha de subtotal. Colunas monetárias são somadas;
    percentuais são recalculados a partir dos totais; PMR usa média simples."""
    total = {}
    for col in ORDEM_COLUNAS:
        if col == "%Lucro Tot":
            total[col] = None
            continue
        if col in COLUNAS_MOEDA:
            total[col] = sum((m.get(col) or 0) for m in lista_metricas)
        elif col == "PMR":
            valores = [m.get('PMR') or 0 for m in lista_metricas]
            total[col] = sum(valores) / len(valores) if valores else 0
        # percentuais recalculados abaixo

    fat = total["Vlr Faturamento"]
    custo = total["Custo Peças"]
    despesa = total["Vlr Despesa"]
    consultas = total["Vlr Consultas"]
    flex = total["Flex"]
    lucro = total["Vlr Lucro S/IRRF"]
    atrasado = total["Inadimplência"]
    avencer = total["Vlr a Vencer"]

    total["%Margem"] = (fat - custo) / custo if custo else 0.0
    total["%Fat"] = (fat - flex) / fat if fat else 0.0
    total["%Despesa"] = despesa / fat if fat else 0.0
    total["%Consultas Fat."] = fat / consultas if consultas else 0.0
    total["%Lucro"] = lucro / fat if fat else 0.0
    total["% Inad/Vencer"] = atrasado / (avencer + atrasado) if (avencer + atrasado) else 0.0
    return total


def preencher_lucro_tot(lista_metricas, lucro_total_grupo):
    """Preenche a coluna '%Lucro Tot' de cada item da lista com a
    participação do lucro daquela filial no lucro total do grupo
    (região, ou geral, dependendo do escopo do relatório)."""
    for m in lista_metricas:
        lucro = m.get("Vlr Lucro S/IRRF") or 0
        m["%Lucro Tot"] = (lucro / lucro_total_grupo) if lucro_total_grupo else 0.0
