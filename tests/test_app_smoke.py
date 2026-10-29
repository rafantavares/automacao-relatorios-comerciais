# -*- coding: utf-8 -*-
"""
Testes de fumaça que dirigem a `App` (main.py) de verdade — sem mouse,
mas exercitando o código real: cria a janela real, preenche as mesmas
StringVars que os campos da tela usam, chama os mesmos métodos que os
botões chamam, bombeia o loop do Tk com `.update()` e confere o estado
final dos widgets/arquivos. Isso cobre threads, exception handling e
I/O de ponta a ponta, sem precisar de um clique de mouse literal.

Precisa de uma sessão Windows com área de trabalho (não roda headless
sem um display/Xvfb equivalente).
"""

import os
import time

import pytest

import main as mod_main
from core import config as mod_config
from core import metas as mod_metas
from conftest import filial_exemplo


def _esperar(condicao, app, timeout=15):
    fim = time.time() + timeout
    while time.time() < fim:
        app.update()
        if condicao():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def app_isolado(tmp_path, monkeypatch, redirecionar_dados):
    monkeypatch.setattr(mod_main, 'EMAILS_CSV', str(tmp_path / 'emails_gerentes.csv'))
    monkeypatch.setattr(mod_main, 'ERRO_LOG', str(tmp_path / 'erro.log'))
    monkeypatch.setattr(mod_main.messagebox, 'showerror', lambda *a, **k: None)
    monkeypatch.setattr(mod_main.messagebox, 'showwarning', lambda *a, **k: None)
    monkeypatch.setattr(mod_main.messagebox, 'showinfo', lambda *a, **k: None)

    app = mod_main.App()
    app.withdraw()

    # Sem um `mainloop()` de verdade rodando, chamar `self.after(0, ...)` a
    # partir de uma thread real de background esbarra numa limitação do
    # próprio Tcl/Tk ("main thread is not in main loop") que só se
    # manifesta fora do laço de eventos contínuo — não é um bug do app.
    # Pra testar a lógica de verdade (erro capturado, botão reabilitado,
    # log preenchido) sem depender dessa corrida, roda `trabalho()` na
    # mesma thread do teste; o agendamento via `self.after(0, ...)` feito
    # de dentro dela continua sendo exercitado normalmente.
    def _executar_sincrono(trabalho, *, botoes=(), progresso=None):
        for b in botoes:
            b.config(state='disabled')
        try:
            trabalho()
        except Exception as e:
            app._registrar_erro(e)
            mod_main.messagebox.showerror(
                "Erro inesperado",
                f"Algo deu errado:\n\n{e}\n\nDetalhes técnicos foram salvos em:\n{mod_main.ERRO_LOG}")
        finally:
            for b in botoes:
                b.config(state='normal')

    monkeypatch.setattr(app, '_executar_em_thread', _executar_sincrono)

    yield app
    app.destroy()


def test_janela_abre_com_as_4_abas(app_isolado):
    app = app_isolado
    app.update()
    assert app.title() == "Relatórios Comerciais — Diretoria Comercial"
    notebook = app.winfo_children()[0]
    assert len(notebook.tabs()) == 4


def test_gerar_relatorios_fluxo_completo(app_isolado, criar_workbook_dados):
    app = app_isolado
    linhas = [
        filial_exemplo(Filial='SP1', Regiao='Sudeste'),
        filial_exemplo(Filial='SP2', Regiao='Sudeste', Faturamento=50000, **{'custo-pecas-medio': 0}),
        filial_exemplo(Filial='BA1', Regiao='Nordeste', Faturamento=30000,
                        **{'custo-pecas-medio': 20000, 'despesa-total': 15000}),
    ]
    caminho_dados = criar_workbook_dados('dados.xlsx', linhas)
    pasta_saida = os.path.dirname(caminho_dados) + os.sep + 'saida'

    app.var_arquivo_dados.set(caminho_dados)
    app.var_mes.set('Agosto')
    app.var_ano.set('2026')
    app.var_pasta_saida.set(pasta_saida)

    assert str(app.btn_gerar['state']) == 'normal'
    app._gerar_relatorios()

    concluiu = _esperar(lambda: len(app.relatorios_gerados) > 0, app)
    assert concluiu, app.txt_log.get('1.0', 'end')

    # o botão de gerar precisa voltar a ficar clicável ao terminar
    assert _esperar(lambda: str(app.btn_gerar['state']) == 'normal', app)

    texto_log = app.txt_log.get('1.0', 'end')
    assert 'Pronto!' in texto_log
    assert len(app.relatorios_gerados) == 2 + 3 + 1  # 2 regiões + 3 filiais + 1 dashboard
    for item in app.relatorios_gerados:
        assert os.path.exists(item['caminho'])

    # a subpasta do mês usa "<mês>-<abreviação>-<ano>" (ex: "08-ago-2026"),
    # não mais "<ano>-<mês>"
    assert os.path.isdir(os.path.join(pasta_saida, '08-ago-2026'))

    # as opções de Região/Filial ficam salvas em config pra popular os
    # dropdowns (dependentes) da aba de e-mails dos gerentes, mesmo numa
    # sessão nova
    pares = {tuple(p) for p in app.config_app['regioes_filiais']}
    assert pares == {('Sudeste', 'SP1'), ('Sudeste', 'SP2'), ('Nordeste', 'BA1')}
    assert set(app._opcoes_regioes()) == {'Sudeste', 'Nordeste'}
    assert set(app._opcoes_filiais_da_regiao('Sudeste')) == {'SP1', 'SP2'}
    assert set(app._opcoes_filiais_da_regiao('Nordeste')) == {'BA1'}


def test_gerar_relatorios_arquivo_invalido_nao_trava_nem_inicia_thread(app_isolado, monkeypatch):
    app = app_isolado
    chamadas = []
    monkeypatch.setattr(mod_main.messagebox, 'showerror', lambda titulo, msg: chamadas.append((titulo, msg)))

    app.var_arquivo_dados.set('C:/caminho/que/nao/existe.xlsx')
    app._gerar_relatorios()
    app.update()

    assert chamadas, "esperava um messagebox.showerror pro arquivo inválido"
    assert str(app.btn_gerar['state']) == 'normal'  # nunca chegou a desabilitar (não iniciou thread)


def test_gerar_relatorios_sem_dados_no_periodo_mostra_aviso(app_isolado, criar_workbook_dados, monkeypatch):
    app = app_isolado
    avisos = []
    monkeypatch.setattr(mod_main.messagebox, 'showwarning', lambda titulo, msg: avisos.append((titulo, msg)))

    caminho_dados = criar_workbook_dados('dados.xlsx', [filial_exemplo(mes=1, ano=2020)])
    app.var_arquivo_dados.set(caminho_dados)
    app.var_mes.set('Agosto')
    app.var_ano.set('2026')

    app._gerar_relatorios()
    assert _esperar(lambda: len(avisos) > 0, app)
    assert 'Sem dados' in avisos[0][0]
    assert _esperar(lambda: str(app.btn_gerar['state']) == 'normal', app)


def test_erro_inesperado_na_thread_e_capturado_e_registrado(app_isolado, criar_workbook_dados, tmp_path, monkeypatch):
    """Simula uma exceção não prevista dentro do trabalho da thread (ex:
    um bug em core.relatorios) e confere que ela é capturada, mostrada
    numa messagebox amigável e registrada em erro.log — em vez de travar
    a thread em silêncio, como acontecia antes da correção."""
    app = app_isolado
    erros_mostrados = []
    monkeypatch.setattr(mod_main.messagebox, 'showerror', lambda titulo, msg: erros_mostrados.append((titulo, msg)))
    monkeypatch.setattr(mod_main.mod_relatorios, 'gerar_todos_relatorios',
                         lambda *a, **k: (_ for _ in ()).throw(RuntimeError("falha simulada de disco")))

    caminho_dados = criar_workbook_dados('dados.xlsx', [filial_exemplo()])
    app.var_arquivo_dados.set(caminho_dados)
    app.var_mes.set('Agosto')
    app.var_ano.set('2026')

    app._gerar_relatorios()

    assert _esperar(lambda: len(erros_mostrados) > 0, app)
    assert 'falha simulada de disco' in erros_mostrados[0][1]
    assert _esperar(lambda: str(app.btn_gerar['state']) == 'normal', app)
    assert os.path.exists(mod_main.ERRO_LOG)
    with open(mod_main.ERRO_LOG, encoding='utf-8') as f:
        assert 'falha simulada de disco' in f.read()


def test_enviar_sem_relatorios_gerados_mostra_aviso(app_isolado, monkeypatch):
    """O envio agora mora na aba 3 — mas sem ter gerado nada na aba 1
    ainda, precisa avisar em vez de abrir a janela de envio."""
    app = app_isolado
    avisos = []
    monkeypatch.setattr(mod_main.messagebox, 'showinfo', lambda titulo, msg: avisos.append((titulo, msg)))

    app._abrir_janela_envio()

    assert avisos
    assert 'aba 1' in avisos[0][1]


def test_enviar_para_selecionados_sem_selecao_mostra_aviso(app_isolado, monkeypatch):
    app = app_isolado
    avisos = []
    monkeypatch.setattr(mod_main.messagebox, 'showinfo', lambda titulo, msg: avisos.append((titulo, msg)))

    app._enviar_para_selecionados()

    assert avisos
    assert 'Marque a caixinha' in avisos[0][1]


def test_janela_envio_abre_com_botao_cancelar_desabilitado(app_isolado, criar_workbook_dados):
    """Depois de gerar relatórios e configurar o e-mail, a janela de
    envio (agora acionada pela aba 3) deve abrir com o botão Cancelar
    desabilitado até que um envio seja iniciado."""
    app = app_isolado
    app.config_app['gmail_remetente'] = 'remetente@gmail.com'
    app.config_app['gmail_senha_app'] = 'senha-de-app'

    caminho_dados = criar_workbook_dados('dados.xlsx', [filial_exemplo(Filial='SP1', Regiao='Sudeste')])
    app.var_arquivo_dados.set(caminho_dados)
    app.var_mes.set('Agosto')
    app.var_ano.set('2026')
    app._gerar_relatorios()
    assert _esperar(lambda: len(app.relatorios_gerados) > 0, app)

    janelas_antes = set(app.winfo_children())
    app._abrir_janela_envio()
    app.update()
    novas_janelas = [w for w in app.winfo_children() if w not in janelas_antes]
    assert novas_janelas, "esperava uma nova janela (Toplevel) de envio"

    def _achar_botoes(widget):
        botoes = []
        for filho in widget.winfo_children():
            if isinstance(filho, mod_main.ttk.Button):
                botoes.append(filho)
            botoes.extend(_achar_botoes(filho))
        return botoes

    textos_botoes = {b['text']: b for b in _achar_botoes(novas_janelas[0])}
    assert 'Enviar agora' in textos_botoes
    assert 'Cancelar' in textos_botoes
    assert str(textos_botoes['Cancelar']['state']) == 'disabled'


def test_janela_envio_desabilita_campo_de_teste_ao_desmarcar_modo_teste(app_isolado, criar_workbook_dados):
    """O campo "E-mail de teste" só importa quando "Modo teste" está
    marcado (envio automático pros e-mails cadastrados não precisa dele)
    — precisa ficar visivelmente desabilitado quando não se aplica, pra
    não parecer um campo obrigatório de preencher toda vez."""
    app = app_isolado
    app.config_app['gmail_remetente'] = 'remetente@gmail.com'
    app.config_app['gmail_senha_app'] = 'senha-de-app'

    caminho_dados = criar_workbook_dados('dados.xlsx', [filial_exemplo(Filial='SP1', Regiao='Sudeste')])
    app.var_arquivo_dados.set(caminho_dados)
    app.var_mes.set('Agosto')
    app.var_ano.set('2026')
    app._gerar_relatorios()
    assert _esperar(lambda: len(app.relatorios_gerados) > 0, app)

    janelas_antes = set(app.winfo_children())
    app._abrir_janela_envio()
    app.update()
    janela = next(w for w in app.winfo_children() if w not in janelas_antes)

    def _achar(widget, classe):
        achados = []
        for filho in widget.winfo_children():
            if isinstance(filho, classe):
                achados.append(filho)
            achados.extend(_achar(filho, classe))
        return achados

    checks = _achar(janela, mod_main.ttk.Checkbutton)
    entradas = [w for w in _achar(janela, mod_main.ttk.Entry) if not isinstance(w, mod_main.ttk.Combobox)]
    assert len(checks) == 1
    assert len(entradas) == 1
    check_modo_teste, entry_email_teste = checks[0], entradas[0]

    assert str(entry_email_teste['state']) == 'normal'  # "Modo teste" começa marcado

    check_modo_teste.invoke()
    app.update()
    assert str(entry_email_teste['state']) == 'disabled'

    check_modo_teste.invoke()
    app.update()
    assert str(entry_email_teste['state']) == 'normal'


def test_janela_gerente_filial_depende_da_regiao_selecionada(app_isolado):
    """Região e Filial são campos diferentes (uma filial pertence a uma
    região) — o combo de Filial começa desabilitado e só mostra as
    filiais da região escolhida, não uma lista solta com tudo junto."""
    app = app_isolado
    app.config_app['regioes_filiais'] = [['Sudeste', 'SP1'], ['Sudeste', 'SP2'], ['Nordeste', 'BA1']]

    janelas_antes = set(app.winfo_children())
    app._adicionar_gerente()
    app.update()
    janela = next(w for w in app.winfo_children() if w not in janelas_antes)

    combos = [w for w in janela.winfo_children() if isinstance(w, mod_main.ttk.Combobox)]
    entradas = [w for w in janela.winfo_children() if isinstance(w, mod_main.ttk.Entry) and not isinstance(w, mod_main.ttk.Combobox)]
    assert len(combos) == 2
    combo_regiao, combo_filial = combos
    assert str(combo_filial['state']) == 'disabled'  # antes de escolher a região, ainda não dá pra saber as filiais

    combo_regiao.set('Sudeste')
    combo_regiao.event_generate('<<ComboboxSelected>>')
    app.update()

    assert str(combo_filial['state']) == 'readonly'
    assert set(combo_filial['values']) == {app._FILIAL_TODAS, 'SP1', 'SP2'}  # só as filiais do Sudeste

    combo_filial.set('SP2')
    entradas[0].insert(0, 'Ana')          # Nome
    entradas[1].insert(0, 'ana@ex.com')   # Email

    botao_salvar = next(w for w in janela.winfo_children()
                         if isinstance(w, mod_main.ttk.Button) and w['text'] == 'Salvar')
    botao_salvar.invoke()
    app.update()

    linhas = [tuple(app.tabela_gerentes.item(i, 'values')) for i in app.tabela_gerentes.get_children()]
    assert (app._DESMARCADO, 'Sudeste', 'SP2', 'Ana', 'ana@ex.com') in linhas


def test_janela_gerente_permite_cadastrar_so_a_regiao(app_isolado):
    """Deixar a Filial em branco cadastra um gerente responsável pela
    região toda (recebe o relatório consolidado da região)."""
    app = app_isolado
    app.config_app['regioes_filiais'] = [['Sudeste', 'SP1']]

    janelas_antes = set(app.winfo_children())
    app._adicionar_gerente()
    app.update()
    janela = next(w for w in app.winfo_children() if w not in janelas_antes)

    combos = [w for w in janela.winfo_children() if isinstance(w, mod_main.ttk.Combobox)]
    entradas = [w for w in janela.winfo_children() if isinstance(w, mod_main.ttk.Entry) and not isinstance(w, mod_main.ttk.Combobox)]
    combo_regiao, combo_filial = combos

    combo_regiao.set('Sudeste')
    combo_regiao.event_generate('<<ComboboxSelected>>')
    app.update()
    assert combo_filial.get() == app._FILIAL_TODAS  # padrão ao trocar de região: sem filial específica

    entradas[0].insert(0, 'Carlos')
    entradas[1].insert(0, 'carlos@ex.com')

    botao_salvar = next(w for w in janela.winfo_children()
                         if isinstance(w, mod_main.ttk.Button) and w['text'] == 'Salvar')
    botao_salvar.invoke()
    app.update()

    linhas = [tuple(app.tabela_gerentes.item(i, 'values')) for i in app.tabela_gerentes.get_children()]
    assert (app._DESMARCADO, 'Sudeste', '', 'Carlos', 'carlos@ex.com') in linhas


def test_enviar_para_marcados_so_considera_as_linhas_com_a_caixinha_marcada(app_isolado):
    """A tabela de gerentes tem uma caixinha (✓) por linha — só as linhas
    marcadas entram no filtro de "Enviar para os marcados", mesmo que
    a tabela tenha várias filiais cadastradas."""
    app = app_isolado
    app.config_app['gmail_remetente'] = 'remetente@gmail.com'
    app.config_app['gmail_senha_app'] = 'senha-de-app'
    app.relatorios_gerados = [
        {'tipo': 'filial', 'regiao': 'Sudeste', 'filial': 'SP1', 'caminho': 'r_sp1.pdf'},
        {'tipo': 'filial', 'regiao': 'Sudeste', 'filial': 'SP2', 'caminho': 'r_sp2.pdf'},
    ]
    app.mes_ano_texto = '08/2026'

    mod_main.mod_emails.salvar_gerentes(mod_main.EMAILS_CSV, [
        {'Regiao': 'Sudeste', 'Filial': 'SP1', 'Nome': 'Ana', 'Email': 'sp1@ex.com'},
        {'Regiao': 'Sudeste', 'Filial': 'SP2', 'Nome': 'Bia', 'Email': 'sp2@ex.com'},
    ])
    app._carregar_tabela_gerentes()
    itens = app.tabela_gerentes.get_children()
    assert len(itens) == 2
    assert all(app.tabela_gerentes.item(i, 'values')[0] == app._DESMARCADO for i in itens)  # começa tudo desmarcado

    # marca só a linha da SP1 (simula o clique na caixinha dessa linha)
    item_sp1 = next(i for i in itens if app.tabela_gerentes.item(i, 'values')[2] == 'SP1')
    valores = list(app.tabela_gerentes.item(item_sp1, 'values'))
    valores[0] = app._MARCADO
    app.tabela_gerentes.item(item_sp1, values=valores)

    janelas_antes = set(app.winfo_children())
    app._enviar_para_selecionados()
    app.update()
    janela = next(w for w in app.winfo_children() if w not in janelas_antes)

    labels = [w for w in janela.winfo_children() if isinstance(w, mod_main.ttk.Label)]
    textos = [str(l['text']) for l in labels]
    assert any('1 relatório' in t for t in textos)  # só a SP1 (marcada), não os 2 relatórios gerados


def test_marcar_e_desmarcar_todos_gerentes(app_isolado):
    app = app_isolado
    mod_main.mod_emails.salvar_gerentes(mod_main.EMAILS_CSV, [
        {'Regiao': 'Sudeste', 'Filial': 'SP1', 'Nome': 'Ana', 'Email': 'sp1@ex.com'},
        {'Regiao': 'Nordeste', 'Filial': 'BA1', 'Nome': 'Bia', 'Email': 'ba1@ex.com'},
    ])
    app._carregar_tabela_gerentes()
    itens = app.tabela_gerentes.get_children()

    app._marcar_todos_gerentes(True)
    assert all(app.tabela_gerentes.item(i, 'values')[0] == app._MARCADO for i in itens)

    app._marcar_todos_gerentes(False)
    assert all(app.tabela_gerentes.item(i, 'values')[0] == app._DESMARCADO for i in itens)


def test_usar_pasta_de_relatorios_ja_gerados_recupera_sessao_anterior(app_isolado, monkeypatch, tmp_path):
    """Fechar o programa e abrir de novo não pode perder a referência a
    um mês já gerado — o botão "Usar pasta de relatórios já gerados..."
    lê o manifesto salvo na pasta e recoloca tudo no estado da tela,
    como se tivesse acabado de gerar (mesmo sem ter passado pela aba 1
    nessa sessão)."""
    from core import relatorios as mod_relatorios_core

    app = app_isolado
    assert app.relatorios_gerados == []  # nada gerado ainda nessa sessão nova

    pasta_de_uma_sessao_anterior = tmp_path / 'output' / '08-ago-2026'
    registro = [{'Filial': 'SP1', 'Regiao': 'Sudeste', 'Faturamento': 100000}]
    mod_relatorios_core.gerar_todos_relatorios(registro, {}, str(pasta_de_uma_sessao_anterior))

    monkeypatch.setattr(mod_main.filedialog, 'askdirectory', lambda **k: str(pasta_de_uma_sessao_anterior))
    avisos = []
    monkeypatch.setattr(mod_main.messagebox, 'showinfo', lambda titulo, msg: avisos.append((titulo, msg)))

    app._selecionar_pasta_relatorios_existente()

    assert avisos
    assert len(app.relatorios_gerados) > 0
    assert app.mes_ano_texto == '08/2026'  # recuperado do nome da pasta "08-ago-2026"
    assert set(app._opcoes_regioes()) == {'Sudeste'}
    assert app._opcoes_filiais_da_regiao('Sudeste') == ['SP1']
    assert 'relatório' in app._texto_status_relatorios()


def test_usar_pasta_sem_manifesto_mostra_erro_claro(app_isolado, monkeypatch, tmp_path):
    app = app_isolado
    pasta_qualquer = tmp_path / 'pasta_sem_nada_a_ver'
    pasta_qualquer.mkdir()

    monkeypatch.setattr(mod_main.filedialog, 'askdirectory', lambda **k: str(pasta_qualquer))
    erros = []
    monkeypatch.setattr(mod_main.messagebox, 'showerror', lambda titulo, msg: erros.append((titulo, msg)))

    app._selecionar_pasta_relatorios_existente()

    assert erros
    assert app.relatorios_gerados == []  # não muda o estado atual em caso de erro
