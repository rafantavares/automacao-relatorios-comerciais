# -*- coding: utf-8 -*-
"""
core/emails.py

Cadastro local (CSV) dos e-mails dos gerentes/representantes de cada
região e filial, e envio automático dos relatórios por Gmail (SMTP com
senha de app — não a senha normal da conta).

Nada aqui envia dados para nenhum servidor além do Gmail do próprio
usuário: a conexão SMTP vai direto do notebook para smtp.gmail.com.
"""

import csv
import os
import smtplib
import ssl
from email.message import EmailMessage

CAMPOS = ['Regiao', 'Filial', 'Nome', 'Email']


class ErroEnvioEmail(Exception):
    pass


def carregar_gerentes(caminho_csv):
    if not os.path.exists(caminho_csv):
        return []
    with open(caminho_csv, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def salvar_gerentes(caminho_csv, gerentes):
    os.makedirs(os.path.dirname(caminho_csv), exist_ok=True)
    with open(caminho_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for g in gerentes:
            w.writerow({k: g.get(k, '') for k in CAMPOS})


def testar_conexao(remetente, senha_app):
    """Só faz login SMTP pra confirmar que as credenciais funcionam, sem
    mandar nenhum e-mail."""
    try:
        contexto = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=contexto, timeout=15) as smtp:
            smtp.login(remetente, senha_app)
        return True, "Conexão OK."
    except smtplib.SMTPAuthenticationError:
        return False, ("Login recusado pelo Gmail. Confira se o e-mail está certo e se "
                        "você está usando uma SENHA DE APP (não a senha normal da conta).")
    except Exception as e:
        return False, f"Falha ao conectar: {e}"


def enviar_relatorio(remetente, senha_app, destinatario, assunto, corpo, caminho_anexo):
    """Manda um e-mail com o relatório anexado. Levanta ErroEnvioEmail se
    algo der errado (login, rede, etc.)."""
    msg = EmailMessage()
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = assunto
    msg.set_content(corpo)

    with open(caminho_anexo, 'rb') as f:
        dados = f.read()
    nome_arquivo = os.path.basename(caminho_anexo)
    msg.add_attachment(
        dados,
        maintype='application',
        subtype='pdf',
        filename=nome_arquivo,
    )

    try:
        contexto = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=contexto, timeout=30) as smtp:
            smtp.login(remetente, senha_app)
            smtp.send_message(msg)
    except Exception as e:
        raise ErroEnvioEmail(f"Falha ao enviar para {destinatario}: {e}")


def enviar_relatorios_gerados(remetente, senha_app, gerentes, relatorios_gerados,
                               mes_ano_texto, progresso=None, modo_teste_email=None,
                               cancelar=None, filtro_destinos=None):
    """
    Percorre os relatórios gerados (ver core.relatorios.gerar_todos_relatorios)
    e manda cada um para o e-mail cadastrado da filial/região correspondente.
    Itens do tipo 'dashboard' são pulados (não têm gerente/e-mail associado).

    Se `modo_teste_email` for informado, TODOS os e-mails vão para esse
    endereço em vez dos gerentes reais (útil pra conferir antes de mandar
    de verdade).

    `cancelar`, se informado, é um objeto com `.is_set()` (ex:
    `threading.Event`) checado a cada iteração — se estiver marcado, o
    envio para imediatamente, sem processar o restante da lista.

    `filtro_destinos`, se informado, é um set de chaves no formato
    `('filial', 'SP1')` / `('regiao', 'Nordeste')` — só os itens cuja
    chave está nesse conjunto são enviados; os demais são ignorados
    (nem aparecem no resultado). `None` (padrão) manda pra todo mundo que
    tiver e-mail cadastrado.

    Devolve uma lista de resultados: [{'destino':, 'email':, 'status':, 'detalhe':}]
    """
    indice_gerentes = {}
    for g in gerentes:
        if g.get('Filial'):
            indice_gerentes[('filial', g['Filial'])] = g
        elif g.get('Regiao'):
            indice_gerentes[('regiao', g['Regiao'])] = g

    resultados = []
    for item in relatorios_gerados:
        if cancelar is not None and cancelar.is_set():
            break
        if item['tipo'] not in ('filial', 'regiao'):
            continue
        if item['tipo'] == 'filial':
            chave = ('filial', item['filial'])
            destino_label = f"Filial {item['filial']}"
        else:
            chave = ('regiao', item['regiao'])
            destino_label = f"Região {item['regiao']}"

        if filtro_destinos is not None and chave not in filtro_destinos:
            continue

        gerente = indice_gerentes.get(chave)
        email_destino = modo_teste_email or (gerente['Email'] if gerente else None)

        if not email_destino:
            resultados.append({'destino': destino_label, 'email': None,
                                'status': 'pulado', 'detalhe': 'Sem e-mail cadastrado'})
            if progresso:
                progresso(f"[pulado] {destino_label}: sem e-mail cadastrado")
            continue

        assunto = f"Relatório Comercial — {destino_label} — {mes_ano_texto}"
        corpo = (f"Olá,\n\nSegue em anexo o relatório de resultado comercial de {mes_ano_texto} "
                 f"referente a {destino_label}.\n\nAtenciosamente,\nDiretoria Comercial")
        try:
            enviar_relatorio(remetente, senha_app, email_destino, assunto, corpo, item['caminho'])
            resultados.append({'destino': destino_label, 'email': email_destino,
                                'status': 'enviado', 'detalhe': ''})
            if progresso:
                progresso(f"[enviado] {destino_label} -> {email_destino}")
        except ErroEnvioEmail as e:
            resultados.append({'destino': destino_label, 'email': email_destino,
                                'status': 'erro', 'detalhe': str(e)})
            if progresso:
                progresso(f"[erro] {destino_label}: {e}")
    return resultados
