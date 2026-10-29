# -*- coding: utf-8 -*-
"""
core/relatorios.py

Gera os arquivos .pdf finais:
  - Um arquivo por REGIÃO (linha de subtotal da região + uma linha por
    filial).
  - Um arquivo por FILIAL, com 3 linhas que mostram dados DIFERENTES entre
    si (Região = subtotal real da região; Filial = métricas da própria
    filial; Total Geral = soma de toda a empresa).
  - Um dashboard geral (com gráficos), cobrindo todas as regiões/filiais
    de uma vez, pra facilitar a leitura rápida do panorama do mês.

As cores de fundo das células seguem esta prioridade:
  1. Se existe META cadastrada para aquela filial+métrica: verde se atingiu
     ou superou a meta, amarelo se ficou entre 90% e 100% da meta,
     vermelho se ficou abaixo de 90% da meta.
  2. Se não existe meta para aquela métrica: usa a regra padrão
     (verde/vermelho pelo sinal, no caso de Vlr Lucro / %Lucro; vermelho
     se % Inad/Vencer > 10%).

Os valores já são calculados em Python (não fórmulas de planilha), então
os PDFs funcionam sozinhos, sem depender de nenhum programa de planilha
pra abrir ou conferir.
"""

import io
import json
import os
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .metricas import (ORDEM_COLUNAS, COLUNAS_MOEDA, COLUNAS_PERCENTUAL,
                        calcular_metricas, somar_metricas, preencher_lucro_tot)

REGIAO_COR = {
    "Centro Oeste": "#FCE4D6",
    "Nordeste":     "#FFF2CC",
    "Norte":        "#E2EFDA",
    "Sudeste":      "#DDEBF7",
    "Sul":          "#E4DFEC",
}
COR_PADRAO_REGIAO = "#E7E6E6"

VERDE_FUNDO, VERDE_TEXTO = "#C6EFCE", "#006100"
AMARELO_FUNDO, AMARELO_TEXTO = "#FFEB9C", "#9C6500"
VERMELHO_FUNDO, VERMELHO_TEXTO = "#FFC7CE", "#9C0006"

HEADER_FUNDO = "#1F3864"
HEADER_TEXTO = "#FFFFFF"
BORDA_COR = "#B7B7B7"

_CORES = {
    'verde': (VERDE_FUNDO, VERDE_TEXTO),
    'amarelo': (AMARELO_FUNDO, AMARELO_TEXTO),
    'vermelho': (VERMELHO_FUNDO, VERMELHO_TEXTO),
}

# Métricas onde "menor é melhor" ao comparar com a meta (despesa, prazo
# médio de recebimento, inadimplência). Para as demais, "maior é melhor".
METRICAS_MENOR_MELHOR = {"%Despesa", "PMR", "% Inad/Vencer"}

PAGESIZE = landscape(A3)
MARGEM = 14 * mm
LARGURA_DISPONIVEL = PAGESIZE[0] - 2 * MARGEM
ALTURA_DISPONIVEL = PAGESIZE[1] - 2 * MARGEM

# Nome do arquivo que guarda, dentro da própria pasta de saída, a lista
# de relatórios gerados (ver `gerar_todos_relatorios`/`carregar_relatorios_gerados`).
# Permite reabrir o programa depois e continuar de onde parou (enviar
# e-mails de um mês já gerado numa sessão anterior), sem precisar gerar
# tudo de novo.
NOME_MANIFESTO = '_relatorios.json'


def _slug(texto):
    return re.sub(r'[^A-Za-z0-9]+', '_', texto).strip('_')


# --------------------------------------------------------- Decisão de cor
def _cor_por_meta_tag(valor, meta, metrica):
    """Devolve 'verde'|'amarelo'|'vermelho', ou None se não há meta pra
    comparar. Função pura (sem nada de PDF), fácil de testar sozinha."""
    if meta is None or meta == 0:
        return None
    if metrica in METRICAS_MENOR_MELHOR:
        atingimento = meta / valor if valor else float('inf')
    else:
        atingimento = valor / meta if meta else 0
    if atingimento >= 1.0:
        return 'verde'
    elif atingimento >= 0.9:
        return 'amarelo'
    return 'vermelho'


def _cor_padrao_tag(coluna, valor):
    """Cor padrão quando não há meta cadastrada pra essa métrica."""
    if coluna in ("Vlr Lucro S/IRRF", "%Lucro"):
        if valor > 0:
            return 'verde'
        elif valor < 0:
            return 'vermelho'
    if coluna == "% Inad/Vencer":
        return 'vermelho' if valor > 0.10 else 'verde'
    return None


def _cor_celula(coluna, valor, metas_linha):
    """Decide a cor final (fundo, texto) de uma célula, ou (None, None)."""
    meta = (metas_linha or {}).get(coluna)
    tag = _cor_por_meta_tag(valor or 0, meta, coluna) if meta is not None else None
    if tag is None:
        tag = _cor_padrao_tag(coluna, valor or 0)
    return _CORES.get(tag, (None, None))


def _formatar_valor(coluna, valor):
    valor = valor or 0
    if coluna in COLUNAS_PERCENTUAL:
        return f"{valor * 100:,.2f}%"
    if coluna in COLUNAS_MOEDA and valor < 0:
        return f"({abs(valor):,.2f})"
    return f"{valor:,.2f}"


# ------------------------------------------------------------- Estilos
_ESTILO_TITULO = ParagraphStyle(name='titulo', fontName='Helvetica-Bold', fontSize=14,
                                 alignment=TA_CENTER, textColor=colors.HexColor('#1F3864'))
_ESTILO_CABECALHO = ParagraphStyle(name='cabecalho', fontName='Helvetica-Bold', fontSize=7,
                                    leading=8, alignment=TA_CENTER, textColor=colors.white)
_ESTILO_CELULA = ParagraphStyle(name='celula', fontName='Helvetica', fontSize=6.5,
                                 leading=8, alignment=TA_CENTER)
_ESTILO_CELULA_NEGRITO = ParagraphStyle(name='celula_b', fontName='Helvetica-Bold', fontSize=6.5,
                                         leading=8, alignment=TA_CENTER)
_ESTILO_ROTULO = ParagraphStyle(name='rotulo', fontName='Helvetica', fontSize=7,
                                 leading=9, alignment=TA_LEFT)
_ESTILO_ROTULO_NEGRITO = ParagraphStyle(name='rotulo_b', fontName='Helvetica-Bold', fontSize=7,
                                         leading=9, alignment=TA_LEFT)
_ESTILO_SUBTITULO = ParagraphStyle(name='subtitulo', fontName='Helvetica-Bold', fontSize=10)
_ESTILO_RESUMO_CEL = ParagraphStyle(name='resumo_cel', fontName='Helvetica', fontSize=8, alignment=TA_CENTER)


def _titulo(texto):
    return Paragraph(texto, _ESTILO_TITULO)


def _montar_tabela_metricas(linhas, largura_disponivel=LARGURA_DISPONIVEL, rotulo_coluna="Filial"):
    """`linhas`: lista de (rotulo, metricas, metas_ou_None, negrito).
    Devolve uma Table pronta, com cabeçalho e cores já aplicadas."""
    cabecalho = [Paragraph(rotulo_coluna, _ESTILO_CABECALHO)] + \
                [Paragraph(c, _ESTILO_CABECALHO) for c in ORDEM_COLUNAS]
    dados = [cabecalho]
    comandos = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(HEADER_FUNDO)),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor(BORDA_COR)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]

    for i, (rotulo, metricas, metas, negrito) in enumerate(linhas, start=1):
        estilo_rotulo = _ESTILO_ROTULO_NEGRITO if negrito else _ESTILO_ROTULO
        estilo_cel = _ESTILO_CELULA_NEGRITO if negrito else _ESTILO_CELULA
        linha_dados = [Paragraph(str(rotulo), estilo_rotulo)]
        for coluna in ORDEM_COLUNAS:
            valor = metricas.get(coluna)
            linha_dados.append(Paragraph(_formatar_valor(coluna, valor), estilo_cel))
        dados.append(linha_dados)

        for c, coluna in enumerate(ORDEM_COLUNAS, start=1):
            valor = metricas.get(coluna)
            fundo, texto_cor = _cor_celula(coluna, valor, metas)
            if fundo:
                comandos.append(('BACKGROUND', (c, i), (c, i), colors.HexColor(fundo)))
                comandos.append(('TEXTCOLOR', (c, i), (c, i), colors.HexColor(texto_cor)))

    largura_rotulo = 26 * mm
    largura_col = (largura_disponivel - largura_rotulo) / len(ORDEM_COLUNAS)
    col_widths = [largura_rotulo] + [largura_col] * len(ORDEM_COLUNAS)

    tabela = Table(dados, colWidths=col_widths, repeatRows=1)
    tabela.setStyle(TableStyle(comandos))
    return tabela


def _tabela_resumo_metas(metricas, metas_filial, largura_disponivel=LARGURA_DISPONIVEL):
    """Mini-resumo Real x Meta x Atingimento pras métricas com meta
    cadastrada. Devolve uma lista de flowables, ou [] se não há metas."""
    if not metas_filial:
        return []

    dados = [[Paragraph(t, _ESTILO_CABECALHO) for t in ("Métrica", "Real", "Meta", "Atingimento")]]
    comandos = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(HEADER_FUNDO)),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor(BORDA_COR)),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]
    for i, (metrica, meta) in enumerate(metas_filial.items(), start=1):
        valor = metricas.get(metrica) or 0
        eh_pct = metrica in COLUNAS_PERCENTUAL
        real_txt = f"{valor * 100:,.2f}%" if eh_pct else f"{valor:,.2f}"
        meta_txt = f"{meta * 100:,.2f}%" if eh_pct else f"{meta:,.2f}"
        atingimento = (meta / valor) if metrica in METRICAS_MENOR_MELHOR and valor else \
                      (valor / meta if meta else 0)
        dados.append([Paragraph(metrica, _ESTILO_RESUMO_CEL), Paragraph(real_txt, _ESTILO_RESUMO_CEL),
                      Paragraph(meta_txt, _ESTILO_RESUMO_CEL), Paragraph(f"{atingimento * 100:,.1f}%", _ESTILO_RESUMO_CEL)])
        tag = _cor_por_meta_tag(valor, meta, metrica)
        if tag:
            fundo, texto_cor = _CORES[tag]
            comandos.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor(fundo)))
            comandos.append(('TEXTCOLOR', (0, i), (-1, i), colors.HexColor(texto_cor)))

    largura_tabela = min(largura_disponivel, 140 * mm)
    col_widths = [largura_tabela * 0.4, largura_tabela * 0.2, largura_tabela * 0.2, largura_tabela * 0.2]
    tabela = Table(dados, colWidths=col_widths)
    tabela.setStyle(TableStyle(comandos))
    return [Paragraph("Comparativo com a meta", _ESTILO_SUBTITULO), Spacer(1, 4), tabela]


def _novo_documento(caminho):
    return SimpleDocTemplate(caminho, pagesize=PAGESIZE,
                              leftMargin=MARGEM, rightMargin=MARGEM,
                              topMargin=MARGEM, bottomMargin=MARGEM)


# --------------------------------------------------------- Agregação
def _agregar(registros):
    """Calcula, a partir dos registros brutos:
      - metricas_por_filial: {filial: metricas}
      - por_regiao: {regiao: [filiais]}
      - subtotal_por_regiao: {regiao: metricas somadas da região}, com
        '%Lucro Tot' de cada filial (dentro de metricas_por_filial) já
        preenchido em relação ao lucro da região.
      - total_geral: metricas somadas de toda a empresa.
    """
    metricas_por_filial = {}
    por_regiao = {}
    for reg in registros:
        metricas_por_filial[reg['Filial']] = calcular_metricas(reg)
        por_regiao.setdefault(reg['Regiao'], []).append(reg['Filial'])

    subtotal_por_regiao = {}
    for regiao, filiais in por_regiao.items():
        metricas_regiao = [metricas_por_filial[f] for f in filiais]
        lucro_regiao = sum((m["Vlr Lucro S/IRRF"] or 0) for m in metricas_regiao)
        preencher_lucro_tot(metricas_regiao, lucro_regiao)
        subtotal = somar_metricas(metricas_regiao)
        subtotal["%Lucro Tot"] = 1.0
        subtotal_por_regiao[regiao] = subtotal

    total_geral = somar_metricas(list(subtotal_por_regiao.values())) if subtotal_por_regiao else somar_metricas([])
    total_geral["%Lucro Tot"] = 1.0
    return metricas_por_filial, por_regiao, subtotal_por_regiao, total_geral


# --------------------------------------------------------- Relatórios
def gerar_relatorio_regiao(regiao, subtotal_regiao, metricas_por_filial, metas_por_filial, pasta_saida):
    """Gera 1 PDF pra região: subtotal da região + 1 linha por filial.
    `metricas_por_filial` é {filial: metricas}, já com '%Lucro Tot' em
    relação ao total da região (ver `_agregar`)."""
    linhas = [(regiao, subtotal_regiao, None, True)]
    for filial in sorted(metricas_por_filial):
        linhas.append(("   " + filial, metricas_por_filial[filial], metas_por_filial.get(filial), False))

    pasta_regiao = os.path.join(pasta_saida, regiao)
    os.makedirs(pasta_regiao, exist_ok=True)
    caminho = os.path.join(pasta_regiao, f"Monitor_Comercio_{_slug(regiao)}.pdf")

    doc = _novo_documento(caminho)
    doc.build([_titulo(f"Resultado Comércio Mensal — {regiao}"), Spacer(1, 8),
               _montar_tabela_metricas(linhas)])
    return caminho


def gerar_relatorio_filial(regiao, filial, metricas_filial, subtotal_regiao, total_geral,
                            metas_por_filial, pasta_saida):
    """Gera 1 PDF pra UMA filial com 3 linhas que mostram dados DIFERENTES:
    Região (subtotal real da região), Filial (métricas da própria filial)
    e Total Geral (soma de toda a empresa) — nunca a mesma linha repetida."""
    metas_filial = metas_por_filial.get(filial)

    lucro_regiao = subtotal_regiao.get("Vlr Lucro S/IRRF") or 0
    lucro_total = total_geral.get("Vlr Lucro S/IRRF") or 0
    linha_regiao = dict(subtotal_regiao)
    linha_regiao["%Lucro Tot"] = (lucro_regiao / lucro_total) if lucro_total else 0.0
    linha_total = dict(total_geral)
    linha_total["%Lucro Tot"] = 1.0

    linhas = [
        (regiao, linha_regiao, None, True),
        (filial, metricas_filial, metas_filial, True),
        ("Total Geral", linha_total, None, True),
    ]

    pasta_regiao = os.path.join(pasta_saida, regiao)
    os.makedirs(pasta_regiao, exist_ok=True)
    caminho = os.path.join(pasta_regiao, f"Monitor_FCA_{_slug(filial)}.pdf")

    elementos = [_titulo(f"Resultado Comércio Mensal — Filial {filial} ({regiao})"), Spacer(1, 8),
                 _montar_tabela_metricas(linhas)]
    resumo = _tabela_resumo_metas(metricas_filial, metas_filial)
    if resumo:
        elementos.append(Spacer(1, 16))
        elementos.extend(resumo)

    doc = _novo_documento(caminho)
    doc.build(elementos)
    return caminho


# --------------------------------------------------------- Dashboard geral
def _grafico_barras(labels, valores, titulo, cor, formato):
    fig, ax = plt.subplots(figsize=(6.3, 3.4), dpi=150)
    ax.bar(labels, valores, color=cor)
    ax.set_title(titulo, fontsize=11, fontweight='bold', color='#1F3864')
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', alpha=0.3)
    if formato == 'moeda':
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _pos: f"{v:,.0f}"))
    else:
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _pos: f"{v * 100:,.0f}%"))
    plt.setp(ax.get_xticklabels(), rotation=30, ha='right', fontsize=8)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf


def _grafico_barras_horizontais(labels, valores, titulo, formato):
    """Gráfico de barras HORIZONTAIS — cada categoria vira uma linha, com
    o rótulo escrito na horizontal (sem precisar girar texto). Diferente
    de `_grafico_barras`, escala bem mesmo com muitas categorias (dezenas
    de filiais): a altura da figura cresce com a quantidade de barras em
    vez de espremer rótulos girados até sobrepor uns nos outros. As
    barras são coloridas por sinal (verde = positivo, vermelho = negativo).
    A altura é limitada a uma página inteira (o reportlab não consegue
    dividir uma imagem única entre páginas — se ultrapassar, a geração do
    PDF quebra) — com muitas filiais, as barras ficam mais finas em vez
    de estourar a página. Devolve (buffer_png, largura_pol, altura_pol)."""
    largura_pol = 12.6
    altura_pol_desejada = max(3.0, 0.28 * len(labels))
    margem_seguranca_pt = 60
    altura_pol_max = (ALTURA_DISPONIVEL - margem_seguranca_pt) * largura_pol / LARGURA_DISPONIVEL
    altura_pol = min(altura_pol_desejada, altura_pol_max)
    fig, ax = plt.subplots(figsize=(largura_pol, altura_pol), dpi=150)
    y_pos = range(len(labels))
    cores = [VERDE_TEXTO if v >= 0 else VERMELHO_TEXTO for v in valores]
    ax.barh(y_pos, valores, color=cores)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()  # primeiro da lista (melhor) fica no topo
    ax.set_title(titulo, fontsize=12, fontweight='bold', color='#1F3864')
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='x', alpha=0.3)
    ax.axvline(0, color='#888888', linewidth=0.8)
    if formato == 'moeda':
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _pos: f"{v:,.0f}"))
    else:
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _pos: f"{v * 100:,.0f}%"))
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf, largura_pol, altura_pol


def gerar_dashboard_geral(metricas_por_filial, subtotal_por_regiao, total_geral, pasta_saida):
    """Gera um único PDF com o panorama de TODAS as regiões/filiais: uma
    tabela resumo (Total Geral + uma linha por região) e 4 gráficos de
    barra. Não é enviado automaticamente a nenhum gerente — fica salvo
    pra quem for analisar o mês como um todo (ex: a diretoria)."""
    lucro_total = total_geral.get("Vlr Lucro S/IRRF") or 0
    linhas = [("Total Geral", total_geral, None, True)]
    for regiao in sorted(subtotal_por_regiao):
        linha_regiao = dict(subtotal_por_regiao[regiao])
        # '%Lucro Tot' no subtotal da região representa "100% de si mesma"
        # (usado no relatório da própria região) — aqui, ao lado de outras
        # regiões e do total da empresa, precisa virar a participação real
        # desta região no lucro total geral.
        lucro_regiao = linha_regiao.get("Vlr Lucro S/IRRF") or 0
        linha_regiao["%Lucro Tot"] = (lucro_regiao / lucro_total) if lucro_total else 0.0
        linhas.append((regiao, linha_regiao, None, False))

    os.makedirs(pasta_saida, exist_ok=True)
    caminho = os.path.join(pasta_saida, "00_Dashboard_Geral.pdf")

    elementos = [_titulo("Panorama Geral — Todas as Regiões"), Spacer(1, 8),
                 _montar_tabela_metricas(linhas, rotulo_coluna="Região"), Spacer(1, 18)]

    if subtotal_por_regiao:
        regioes_ord = sorted(subtotal_por_regiao)
        cores_regiao = [REGIAO_COR.get(r, COR_PADRAO_REGIAO) for r in regioes_ord]

        graf_fat = _grafico_barras(regioes_ord,
                                    [subtotal_por_regiao[r]["Vlr Faturamento"] for r in regioes_ord],
                                    "Faturamento por Região", cores_regiao, 'moeda')
        graf_lucro = _grafico_barras(regioes_ord,
                                      [subtotal_por_regiao[r]["Vlr Lucro S/IRRF"] for r in regioes_ord],
                                      "Lucro por Região", cores_regiao, 'moeda')
        graf_inad = _grafico_barras(regioes_ord,
                                     [subtotal_por_regiao[r]["% Inad/Vencer"] for r in regioes_ord],
                                     "% Inadimplência/Vencer por Região", cores_regiao, 'percentual')

        largura_img = LARGURA_DISPONIVEL / 2 - 4 * mm
        altura_img = largura_img * 3.4 / 6.3
        linha1 = Table([[Image(graf_fat, width=largura_img, height=altura_img),
                          Image(graf_lucro, width=largura_img, height=altura_img)]])
        elementos.extend([linha1, Spacer(1, 10),
                           Image(graf_inad, width=LARGURA_DISPONIVEL, height=LARGURA_DISPONIVEL * 3.4 / 6.3),
                           Spacer(1, 14)])

        # %Lucro por filial, em largura total: gráfico horizontal (uma
        # barra por linha) pra não sobrepor rótulos quando há muitas
        # filiais — diferente dos gráficos por região (só 5 categorias),
        # aqui a quantidade de barras cresce junto com o cadastro.
        filiais_ord = sorted(metricas_por_filial, key=lambda f: metricas_por_filial[f]["%Lucro"], reverse=True)
        graf_plucro, largura_pol, altura_pol = _grafico_barras_horizontais(
            filiais_ord, [metricas_por_filial[f]["%Lucro"] for f in filiais_ord],
            "%Lucro por Filial (do melhor pro pior)", 'percentual')
        altura_img_plucro = LARGURA_DISPONIVEL * (altura_pol / largura_pol)
        elementos.append(Image(graf_plucro, width=LARGURA_DISPONIVEL, height=altura_img_plucro))

    doc = _novo_documento(caminho)
    doc.build(elementos)
    return caminho


# --------------------------------------------------------- Orquestração
def gerar_todos_relatorios(registros, metas_por_filial, pasta_saida, progresso=None):
    """Gera os PDFs de todas as regiões, todas as filiais e o dashboard
    geral, a partir de `registros`. `progresso`, se fornecido, é chamado
    com uma string a cada arquivo gerado. Devolve a lista de arquivos
    gerados: [{'tipo': 'filial'|'regiao'|'dashboard', 'regiao':, 'filial':,
    'caminho':}]."""
    metricas_por_filial, por_regiao, subtotal_por_regiao, total_geral = _agregar(registros)

    os.makedirs(pasta_saida, exist_ok=True)
    gerados = []

    for regiao in sorted(por_regiao):
        filiais = por_regiao[regiao]
        metricas_regiao = {f: metricas_por_filial[f] for f in filiais}
        caminho = gerar_relatorio_regiao(regiao, subtotal_por_regiao[regiao], metricas_regiao,
                                          metas_por_filial, pasta_saida)
        gerados.append({'tipo': 'regiao', 'regiao': regiao, 'filial': None, 'caminho': caminho})
        if progresso:
            progresso(f"Região {regiao} -> {os.path.basename(caminho)}")

        for filial in sorted(filiais):
            caminho_f = gerar_relatorio_filial(regiao, filial, metricas_por_filial[filial],
                                                subtotal_por_regiao[regiao], total_geral,
                                                metas_por_filial, pasta_saida)
            gerados.append({'tipo': 'filial', 'regiao': regiao, 'filial': filial, 'caminho': caminho_f})
            if progresso:
                progresso(f"  Filial {filial} -> {os.path.basename(caminho_f)}")

    caminho_dash = gerar_dashboard_geral(metricas_por_filial, subtotal_por_regiao, total_geral, pasta_saida)
    gerados.append({'tipo': 'dashboard', 'regiao': None, 'filial': None, 'caminho': caminho_dash})
    if progresso:
        progresso(f"Dashboard geral -> {os.path.basename(caminho_dash)}")

    _salvar_manifesto(gerados, pasta_saida)
    return gerados


def _salvar_manifesto(gerados, pasta_saida):
    """Salva a lista de relatórios gerados num arquivo json dentro da
    própria pasta de saída, com caminhos relativos (funciona mesmo se a
    pasta for movida/copiada depois). É isso que `carregar_relatorios_gerados`
    lê pra reconhecer uma pasta já gerada numa sessão anterior."""
    manifesto = [
        {'tipo': g['tipo'], 'regiao': g['regiao'], 'filial': g['filial'],
         'caminho': os.path.relpath(g['caminho'], pasta_saida)}
        for g in gerados
    ]
    with open(os.path.join(pasta_saida, NOME_MANIFESTO), 'w', encoding='utf-8') as f:
        json.dump(manifesto, f, ensure_ascii=False, indent=2)


def carregar_relatorios_gerados(pasta_saida):
    """Lê o manifesto salvo por uma geração anterior (`gerar_todos_relatorios`)
    dentro de `pasta_saida`, e devolve a lista de relatórios no mesmo
    formato de retorno de `gerar_todos_relatorios`: [{'tipo':, 'regiao':,
    'filial':, 'caminho':}], com os caminhos resolvidos como absolutos a
    partir de `pasta_saida`. Arquivos individuais que não existem mais
    (apagados à mão, por exemplo) são simplesmente ignorados.

    Levanta FileNotFoundError se essa pasta não tiver um manifesto — ou
    porque nunca foi gerada por este programa, ou porque é de uma versão
    antiga de antes desse recurso existir."""
    caminho_manifesto = os.path.join(pasta_saida, NOME_MANIFESTO)
    if not os.path.exists(caminho_manifesto):
        raise FileNotFoundError(caminho_manifesto)
    with open(caminho_manifesto, encoding='utf-8') as f:
        manifesto = json.load(f)

    gerados = []
    for item in manifesto:
        caminho_abs = os.path.normpath(os.path.join(pasta_saida, item['caminho']))
        if os.path.exists(caminho_abs):
            gerados.append({'tipo': item['tipo'], 'regiao': item['regiao'],
                             'filial': item['filial'], 'caminho': caminho_abs})
    return gerados
