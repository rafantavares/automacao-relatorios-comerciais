# -*- coding: utf-8 -*-
"""Testa core/emails.py: round-trip do cadastro de gerentes e a lógica
de roteamento de envio (prioridade filial > região, modo teste, cancelar
no meio da lista, filtro de destinos, e o caso "sem e-mail cadastrado")
— sem nenhuma conexão SMTP real."""

import os
import threading

import pytest

from core import emails as mod_emails


def test_salvar_e_carregar_gerentes_roundtrip(tmp_path):
    caminho = str(tmp_path / 'sub' / 'emails.csv')
    gerentes = [
        {'Regiao': 'Sudeste', 'Filial': 'SP1', 'Nome': 'Ana', 'Email': 'ana@ex.com'},
        {'Regiao': 'Nordeste', 'Filial': '', 'Nome': 'Bruno', 'Email': 'bruno@ex.com'},
    ]
    mod_emails.salvar_gerentes(caminho, gerentes)
    assert os.path.exists(caminho)

    carregados = mod_emails.carregar_gerentes(caminho)
    assert carregados == gerentes


def test_carregar_gerentes_arquivo_inexistente_devolve_lista_vazia(tmp_path):
    assert mod_emails.carregar_gerentes(str(tmp_path / 'nao_existe.csv')) == []


def _relatorios_exemplo():
    return [
        {'tipo': 'filial', 'regiao': 'Sudeste', 'filial': 'SP1', 'caminho': 'r_sp1.xlsx'},
        {'tipo': 'filial', 'regiao': 'Sudeste', 'filial': 'SP2', 'caminho': 'r_sp2.xlsx'},
        {'tipo': 'regiao', 'regiao': 'Sudeste', 'filial': None, 'caminho': 'r_regiao.xlsx'},
    ]


def test_envio_prioriza_email_da_filial_sobre_o_da_regiao(monkeypatch):
    enviados = []
    monkeypatch.setattr(mod_emails, 'enviar_relatorio',
                         lambda remetente, senha, destino, assunto, corpo, anexo: enviados.append((destino, anexo)))

    gerentes = [
        {'Regiao': 'Sudeste', 'Filial': 'SP1', 'Nome': 'Ana', 'Email': 'sp1@ex.com'},
        {'Regiao': 'Sudeste', 'Filial': '', 'Nome': 'Bruno', 'Email': 'regiao@ex.com'},
    ]
    resultados = mod_emails.enviar_relatorios_gerados(
        'remetente@gmail.com', 'senha', gerentes, _relatorios_exemplo(), '08/2026')

    por_destino = {r['destino']: r for r in resultados}
    assert por_destino['Filial SP1']['status'] == 'enviado'
    assert por_destino['Filial SP1']['email'] == 'sp1@ex.com'
    assert por_destino['Filial SP2']['status'] == 'pulado'  # sem e-mail cadastrado pra SP2
    assert por_destino['Região Sudeste']['status'] == 'enviado'
    assert por_destino['Região Sudeste']['email'] == 'regiao@ex.com'
    assert ('sp1@ex.com', 'r_sp1.xlsx') in enviados
    assert ('regiao@ex.com', 'r_regiao.xlsx') in enviados


def test_modo_teste_manda_tudo_para_um_unico_email(monkeypatch):
    enviados = []
    monkeypatch.setattr(mod_emails, 'enviar_relatorio',
                         lambda remetente, senha, destino, assunto, corpo, anexo: enviados.append(destino))

    gerentes = [{'Regiao': 'Sudeste', 'Filial': 'SP1', 'Nome': 'Ana', 'Email': 'sp1@ex.com'}]
    resultados = mod_emails.enviar_relatorios_gerados(
        'remetente@gmail.com', 'senha', gerentes, _relatorios_exemplo(), '08/2026',
        modo_teste_email='teste@gmail.com')

    assert all(status == 'enviado' for status in (r['status'] for r in resultados))
    assert set(enviados) == {'teste@gmail.com'}


def test_sem_email_cadastrado_fica_pulado_sem_levantar_erro():
    resultados = mod_emails.enviar_relatorios_gerados(
        'remetente@gmail.com', 'senha', [], _relatorios_exemplo(), '08/2026')
    assert all(r['status'] == 'pulado' for r in resultados)
    assert all(r['email'] is None for r in resultados)


def test_erro_no_envio_de_um_relatorio_nao_interrompe_os_outros(monkeypatch):
    def enviar_com_falha_no_primeiro(remetente, senha, destino, assunto, corpo, anexo):
        if destino == 'sp1@ex.com':
            raise mod_emails.ErroEnvioEmail('falha simulada')

    monkeypatch.setattr(mod_emails, 'enviar_relatorio', enviar_com_falha_no_primeiro)

    gerentes = [
        {'Regiao': 'Sudeste', 'Filial': 'SP1', 'Nome': 'Ana', 'Email': 'sp1@ex.com'},
        {'Regiao': 'Sudeste', 'Filial': 'SP2', 'Nome': 'Bia', 'Email': 'sp2@ex.com'},
    ]
    resultados = mod_emails.enviar_relatorios_gerados(
        'remetente@gmail.com', 'senha', gerentes, _relatorios_exemplo(), '08/2026')

    por_destino = {r['destino']: r for r in resultados}
    assert por_destino['Filial SP1']['status'] == 'erro'
    assert por_destino['Filial SP2']['status'] == 'enviado'


def test_cancelar_interrompe_envio_no_meio_da_lista(monkeypatch):
    """Simula o usuário clicando "Cancelar" logo depois do 1º e-mail —
    os itens seguintes da lista não devem nem ser processados."""
    enviados = []
    evento = threading.Event()

    def enviar_e_cancelar(remetente, senha, destino, assunto, corpo, anexo):
        enviados.append(destino)
        evento.set()

    monkeypatch.setattr(mod_emails, 'enviar_relatorio', enviar_e_cancelar)

    gerentes = [
        {'Regiao': 'Sudeste', 'Filial': 'SP1', 'Nome': 'Ana', 'Email': 'sp1@ex.com'},
        {'Regiao': 'Sudeste', 'Filial': 'SP2', 'Nome': 'Bia', 'Email': 'sp2@ex.com'},
    ]
    resultados = mod_emails.enviar_relatorios_gerados(
        'remetente@gmail.com', 'senha', gerentes, _relatorios_exemplo(), '08/2026', cancelar=evento)

    assert enviados == ['sp1@ex.com']
    assert len(resultados) == 1  # parou de processar os itens seguintes da lista


def test_filtro_destinos_so_envia_pros_filtrados(monkeypatch):
    enviados = []
    monkeypatch.setattr(mod_emails, 'enviar_relatorio',
                         lambda remetente, senha, destino, assunto, corpo, anexo: enviados.append(destino))

    gerentes = [
        {'Regiao': 'Sudeste', 'Filial': 'SP1', 'Nome': 'Ana', 'Email': 'sp1@ex.com'},
        {'Regiao': 'Sudeste', 'Filial': 'SP2', 'Nome': 'Bia', 'Email': 'sp2@ex.com'},
        {'Regiao': 'Sudeste', 'Filial': '', 'Nome': 'Carlos', 'Email': 'regiao@ex.com'},
    ]
    resultados = mod_emails.enviar_relatorios_gerados(
        'remetente@gmail.com', 'senha', gerentes, _relatorios_exemplo(), '08/2026',
        filtro_destinos={('filial', 'SP1')})

    assert enviados == ['sp1@ex.com']
    assert len(resultados) == 1
    assert resultados[0]['destino'] == 'Filial SP1'


def test_item_dashboard_e_sempre_pulado(monkeypatch):
    """O dashboard geral não pertence a nenhum gerente/filial específico
    — não deve gerar nenhuma tentativa de envio nem linha de resultado."""
    enviados = []
    monkeypatch.setattr(mod_emails, 'enviar_relatorio',
                         lambda remetente, senha, destino, assunto, corpo, anexo: enviados.append(destino))

    relatorios = _relatorios_exemplo() + [
        {'tipo': 'dashboard', 'regiao': None, 'filial': None, 'caminho': 'dashboard.pdf'}]
    gerentes = [{'Regiao': 'Sudeste', 'Filial': 'SP1', 'Nome': 'Ana', 'Email': 'sp1@ex.com'}]

    resultados = mod_emails.enviar_relatorios_gerados(
        'remetente@gmail.com', 'senha', gerentes, relatorios, '08/2026')

    assert len(resultados) == len(_relatorios_exemplo())
    assert 'dashboard.pdf' not in [r.get('caminho') for r in resultados]
