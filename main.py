# -*- coding: utf-8 -*-
"""
Relatórios Comerciais — programa local para gerar e enviar os relatórios
mensais de resultado comercial por região e por filial.

Como rodar:
    python main.py

Requisitos: Python 3.9+ e a biblioteca openpyxl (veja requirements.txt).
Tkinter já vem junto com o Python no Windows/Mac; no Linux às vezes é
preciso instalar o pacote "python3-tk" separadamente.

Este programa é 100% local: os dados financeiros nunca saem do
notebook, exceto os relatórios que VOCÊ decidir mandar por e-mail pela
aba "Enviar por E-mail".
"""

import datetime
import os
import re
import sys
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

if getattr(sys, 'frozen', False):
    sys.path.insert(0, sys._MEIPASS)
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Em monitores Windows com escala >100% (o padrão na maioria dos notebooks
# hoje), o Tkinter sem isso renderiza a janela borrada/minúscula. Precisa
# rodar antes de qualquer widget ser criado.
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from core import dados as mod_dados
from core import metas as mod_metas
from core import relatorios as mod_relatorios
from core import emails as mod_emails
from core import config as mod_config
from core.appdir import base_dir, bootstrap_dados_iniciais, NOME_PASTA_DADOS

APP_DIR = base_dir()
EMAILS_CSV = os.path.join(APP_DIR, NOME_PASTA_DADOS, 'emails_gerentes.csv')
ERRO_LOG = os.path.join(APP_DIR, NOME_PASTA_DADOS, 'erro.log')

MESES = [
    (1, "Janeiro"), (2, "Fevereiro"), (3, "Março"), (4, "Abril"),
    (5, "Maio"), (6, "Junho"), (7, "Julho"), (8, "Agosto"),
    (9, "Setembro"), (10, "Outubro"), (11, "Novembro"), (12, "Dezembro"),
]
MESES_ABREV = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun',
               'jul', 'ago', 'set', 'out', 'nov', 'dez']


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Relatórios Comerciais — Diretoria Comercial")
        self.geometry("980x680")
        self.minsize(860, 600)

        self.config_app = mod_config.carregar()

        self.registros_atuais = []
        self.mes_ano_texto = ""
        self.relatorios_gerados = []
        self.metas_por_filial = {}

        self._montar_interface()

    # ------------------------------------------------------------- Erros
    def report_callback_exception(self, exc, val, tb):
        """Chamado automaticamente pelo Tkinter quando um callback de botão/
        widget levanta uma exceção não tratada. Sem isso, sob `pythonw.exe`
        (sem console), o erro simplesmente desapareceria e a tela pareceria
        travada, sem nenhuma pista pro usuário."""
        self._registrar_erro(val)
        messagebox.showerror(
            "Erro inesperado",
            f"Algo deu errado:\n\n{val}\n\n"
            f"Detalhes técnicos foram salvos em:\n{ERRO_LOG}")

    def _registrar_erro(self, exc):
        try:
            os.makedirs(os.path.dirname(ERRO_LOG), exist_ok=True)
            with open(ERRO_LOG, 'a', encoding='utf-8') as f:
                f.write(f"\n--- {datetime.datetime.now().isoformat(timespec='seconds')} ---\n")
                traceback.print_exc(file=f)
        except Exception:
            pass

    def _executar_em_thread(self, trabalho, *, botoes=(), progresso=None):
        """Roda `trabalho` (função sem argumentos) numa thread separada,
        pra não travar a interface. Desabilita `botoes` enquanto roda,
        anima `progresso` (um ttk.Progressbar indeterminado, se houver), e
        reabilita tudo ao terminar — com sucesso ou erro. Qualquer exceção
        não prevista dentro de `trabalho` é capturada aqui, gravada em
        ERRO_LOG e mostrada numa mensagem amigável, em vez de travar
        a thread em silêncio (o que aconteceria sem isso, já que o programa
        roda via pythonw.exe, sem console pra mostrar o erro)."""
        for b in botoes:
            b.config(state='disabled')
        if progresso is not None:
            progresso.start(12)

        def finalizar():
            for b in botoes:
                b.config(state='normal')
            if progresso is not None:
                progresso.stop()

        def _run():
            try:
                trabalho()
            except Exception as e:
                self._registrar_erro(e)
                self.after(0, lambda: messagebox.showerror(
                    "Erro inesperado",
                    f"Algo deu errado:\n\n{e}\n\n"
                    f"Detalhes técnicos foram salvos em:\n{ERRO_LOG}"))
            finally:
                self.after(0, finalizar)

        threading.Thread(target=_run, daemon=True).start()

    # ------------------------------------------------------------------ UI
    def _montar_interface(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill='both', expand=True, padx=8, pady=8)

        self.aba_gerar = ttk.Frame(notebook)
        self.aba_metas = ttk.Frame(notebook)
        self.aba_gerentes = ttk.Frame(notebook)
        self.aba_email_config = ttk.Frame(notebook)

        notebook.add(self.aba_gerar, text="1. Gerar Relatórios")
        notebook.add(self.aba_metas, text="2. Metas por Filial")
        notebook.add(self.aba_gerentes, text="3. E-mails dos Gerentes")
        notebook.add(self.aba_email_config, text="4. Config. de E-mail (Gmail)")

        self._montar_aba_gerar()
        self._montar_aba_metas()
        self._montar_aba_gerentes()
        self._montar_aba_email_config()

    # ---------------------------------------------------------- Aba 1: Gerar
    def _montar_aba_gerar(self):
        f = self.aba_gerar
        pad = {'padx': 8, 'pady': 6}

        bloco = ttk.LabelFrame(f, text="Arquivo de dados mensal (.xlsm / .xlsx)")
        bloco.pack(fill='x', **pad)
        self.var_arquivo_dados = tk.StringVar(value=self.config_app.get('ultimo_arquivo_dados', ''))
        ttk.Entry(bloco, textvariable=self.var_arquivo_dados, width=70).pack(side='left', padx=8, pady=8)
        ttk.Button(bloco, text="Selecionar arquivo...", command=self._selecionar_arquivo_dados).pack(side='left', padx=4)

        bloco2 = ttk.LabelFrame(f, text="Período")
        bloco2.pack(fill='x', **pad)
        ttk.Label(bloco2, text="Mês:").pack(side='left', padx=(8, 2))
        self.var_mes = tk.StringVar()
        combo_mes = ttk.Combobox(bloco2, textvariable=self.var_mes, state='readonly', width=12,
                                  values=[nome for _, nome in MESES])
        combo_mes.pack(side='left')
        ttk.Label(bloco2, text="Ano:").pack(side='left', padx=(16, 2))
        self.var_ano = tk.StringVar()
        ttk.Entry(bloco2, textvariable=self.var_ano, width=8).pack(side='left')

        agora = datetime.date.today()
        combo_mes.set(MESES[agora.month - 1][1])
        self.var_ano.set(str(agora.year))

        bloco3 = ttk.LabelFrame(f, text="Pasta de saída dos relatórios")
        bloco3.pack(fill='x', **pad)
        self.var_pasta_saida = tk.StringVar(value=self.config_app.get('pasta_saida'))
        ttk.Entry(bloco3, textvariable=self.var_pasta_saida, width=70).pack(side='left', padx=8, pady=8)
        ttk.Button(bloco3, text="Selecionar pasta...", command=self._selecionar_pasta_saida).pack(side='left', padx=4)

        botoes = ttk.Frame(f)
        botoes.pack(fill='x', **pad)
        self.btn_gerar = ttk.Button(botoes, text="Gerar relatórios (região + filial)",
                                     command=self._gerar_relatorios)
        self.btn_gerar.pack(side='left', padx=4)

        self.progress_gerar = ttk.Progressbar(f, mode='indeterminate')
        self.progress_gerar.pack(fill='x', padx=8, pady=(0, 4))

        ttk.Label(f, text="Andamento:").pack(anchor='w', padx=8)
        frame_log = ttk.Frame(f)
        frame_log.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self.txt_log = tk.Text(frame_log, height=18, wrap='word')
        scroll_log = ttk.Scrollbar(frame_log, orient='vertical', command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scroll_log.set)
        self.txt_log.pack(side='left', fill='both', expand=True)
        scroll_log.pack(side='right', fill='y')

    def _log(self, msg):
        self.txt_log.insert('end', msg + "\n")
        self.txt_log.see('end')
        self.update_idletasks()

    def _selecionar_arquivo_dados(self):
        caminho = filedialog.askopenfilename(
            title="Selecione o arquivo mensal da diretoria",
            filetypes=[("Excel", "*.xlsm *.xlsx")])
        if caminho:
            self.var_arquivo_dados.set(caminho)

    def _selecionar_pasta_saida(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta onde salvar os relatórios")
        if pasta:
            self.var_pasta_saida.set(pasta)

    def _gerar_relatorios(self):
        caminho = self.var_arquivo_dados.get().strip()
        if not caminho or not os.path.exists(caminho):
            messagebox.showerror("Erro", "Selecione um arquivo de dados válido primeiro.")
            return
        try:
            mes_num = MESES[[nome for _, nome in MESES].index(self.var_mes.get())][0]
            ano_num = int(self.var_ano.get())
        except Exception:
            messagebox.showerror("Erro", "Confira o mês e o ano selecionados.")
            return

        pasta_saida_base = self.var_pasta_saida.get().strip() or mod_config.PADRAO['pasta_saida']
        pasta_saida = os.path.join(pasta_saida_base, f"{mes_num:02d}-{MESES_ABREV[mes_num - 1]}-{ano_num:04d}")

        self.txt_log.delete('1.0', 'end')
        self._log(f"Lendo dados de {os.path.basename(caminho)} — {mes_num:02d}/{ano_num}...")

        def trabalho():
            try:
                registros = mod_dados.carregar_dados_mensais(caminho, mes=mes_num, ano=ano_num, unidade='Comércio')
            except mod_dados.ErroLeituraDados as e:
                self.after(0, lambda: messagebox.showerror("Erro ao ler dados", str(e)))
                return
            if not registros:
                self.after(0, lambda: messagebox.showwarning(
                    "Sem dados",
                    f"Não encontrei nenhum registro de Comércio para {mes_num:02d}/{ano_num} nesse arquivo.\n\n"
                    "Confira se o mês e o ano selecionados estão certos e se a planilha "
                    "realmente tem linhas para esse período."))
                return

            self.after(0, lambda: self._log(f"{len(registros)} filiais encontradas."))

            metas_por_filial, aviso_metas = self._carregar_metas_configuradas()
            if aviso_metas:
                self.after(0, lambda: self._log(aviso_metas))
            elif metas_por_filial:
                self.after(0, lambda: self._log(f"Metas carregadas para {len(metas_por_filial)} filiais."))
            else:
                self.after(0, lambda: self._log("Nenhuma meta configurada — usando só as cores padrão (verde/vermelho por lucro)."))

            gerados = mod_relatorios.gerar_todos_relatorios(
                registros, metas_por_filial, pasta_saida,
                progresso=lambda m: self.after(0, lambda m=m: self._log(m)))

            self.registros_atuais = registros
            self.relatorios_gerados = gerados
            self.mes_ano_texto = f"{mes_num:02d}/{ano_num}"
            self.metas_por_filial = metas_por_filial

            pares_regiao_filial = sorted({(r['Regiao'], r['Filial']) for r in registros})

            self.config_app['ultimo_arquivo_dados'] = caminho
            self.config_app['pasta_saida'] = pasta_saida_base
            self.config_app['regioes_filiais'] = [list(p) for p in pares_regiao_filial]
            mod_config.salvar(self.config_app)

            self.after(0, lambda: self._log(
                f"\nPronto! {len(gerados)} arquivos gerados em:\n{pasta_saida}\n"
                'Vá para a aba "3. E-mails dos Gerentes" pra enviar por e-mail.'))
            self.after(0, self._atualizar_status_relatorios)

        self._executar_em_thread(trabalho, botoes=[self.btn_gerar], progresso=self.progress_gerar)

    def _carregar_metas_configuradas(self):
        """Devolve (metas_por_filial, aviso). `aviso` é None se tudo correu
        bem, ou uma mensagem pra logar se as metas configuradas não
        puderam ser carregadas. Não mexe em widgets diretamente — quem
        chama decide como/quando mostrar isso na tela (esta função roda
        dentro da thread de trabalho, e o Tkinter não é thread-safe)."""
        cfg = mod_metas.carregar_config_mapeamento()
        if not cfg:
            return {}, None
        try:
            return mod_metas.carregar_metas(cfg['caminho_arquivo'], cfg['aba'], cfg['mapeamento']), None
        except Exception as e:
            return {}, f"Aviso: não consegui carregar as metas ({e}). Seguindo sem metas."

    # ---------------------------------------------------------- Aba 2: Metas
    def _montar_aba_metas(self):
        f = self.aba_metas
        pad = {'padx': 8, 'pady': 6}

        ttk.Label(f, text=(
            "A planilha de metas pode mudar de formato de mês a mês. Sempre que isso "
            "acontecer, carregue o novo arquivo aqui e refaça o mapeamento das colunas — "
            "não precisa mexer em nada além disso."
        ), wraplength=900, justify='left').pack(anchor='w', **pad)

        bloco = ttk.LabelFrame(f, text="Arquivo de metas")
        bloco.pack(fill='x', **pad)
        self.var_arquivo_metas = tk.StringVar()
        ttk.Entry(bloco, textvariable=self.var_arquivo_metas, width=70).pack(side='left', padx=8, pady=8)
        ttk.Button(bloco, text="Selecionar arquivo...", command=self._selecionar_arquivo_metas).pack(side='left', padx=4)
        ttk.Button(bloco, text="Carregar colunas", command=self._carregar_cabecalhos_metas).pack(side='left', padx=4)

        self.frame_mapeamento = ttk.LabelFrame(f, text="Mapeamento de colunas")
        self.frame_mapeamento.pack(fill='both', expand=True, **pad)
        self.combos_mapeamento = {}
        self._construir_area_mapeamento([])

        ttk.Button(f, text="Salvar mapeamento", command=self._salvar_mapeamento_metas).pack(anchor='e', padx=8, pady=8)

        self.lbl_status_metas = ttk.Label(f, text="")
        self.lbl_status_metas.pack(anchor='w', padx=8)

        cfg = mod_metas.carregar_config_mapeamento()
        if cfg:
            self.lbl_status_metas.config(
                text=f"Mapeamento atual: {os.path.basename(cfg['caminho_arquivo'])} (aba '{cfg['aba']}')")

    def _selecionar_arquivo_metas(self):
        caminho = filedialog.askopenfilename(title="Selecione a planilha de metas",
                                              filetypes=[("Excel", "*.xlsx *.xlsm *.xls")])
        if caminho:
            self.var_arquivo_metas.set(caminho)

    def _carregar_cabecalhos_metas(self):
        caminho = self.var_arquivo_metas.get().strip()
        if not caminho or not os.path.exists(caminho):
            messagebox.showerror("Erro", "Selecione um arquivo de metas válido primeiro.")
            return
        try:
            abas = mod_metas.listar_abas(caminho)
            aba = abas[0]
            cabecalhos = mod_metas.ler_cabecalhos(caminho, aba)
        except Exception as e:
            messagebox.showerror("Erro ao ler planilha", str(e))
            return
        self._aba_metas_atual = aba
        self._construir_area_mapeamento(cabecalhos)

    def _construir_area_mapeamento(self, cabecalhos):
        for widget in self.frame_mapeamento.winfo_children():
            widget.destroy()
        self.combos_mapeamento = {}

        opcoes = [''] + cabecalhos
        linha = 0
        ttk.Label(self.frame_mapeamento, text="Coluna que identifica a Filial (obrigatório):",
                  width=42, anchor='w').grid(row=linha, column=0, sticky='w', padx=6, pady=4)
        combo = ttk.Combobox(self.frame_mapeamento, values=opcoes, state='readonly', width=30)
        combo.grid(row=linha, column=1, padx=6, pady=4)
        self.combos_mapeamento['coluna_filial'] = combo
        linha += 1

        for metrica in mod_metas.METRICAS_COM_META:
            ttk.Label(self.frame_mapeamento, text=f"Meta de: {metrica}",
                      width=42, anchor='w').grid(row=linha, column=0, sticky='w', padx=6, pady=4)
            combo = ttk.Combobox(self.frame_mapeamento, values=opcoes, state='readonly', width=30)
            combo.grid(row=linha, column=1, padx=6, pady=4)
            self.combos_mapeamento[metrica] = combo
            linha += 1

        # se já existe um mapeamento salvo pro mesmo arquivo/aba, pré-seleciona
        cfg = mod_metas.carregar_config_mapeamento()
        if cfg and cabecalhos:
            for chave, combo in self.combos_mapeamento.items():
                valor_salvo = cfg['mapeamento'].get(chave, '')
                if valor_salvo in cabecalhos:
                    combo.set(valor_salvo)

    def _salvar_mapeamento_metas(self):
        caminho = self.var_arquivo_metas.get().strip()
        if not caminho:
            messagebox.showerror("Erro", "Selecione e carregue um arquivo de metas primeiro.")
            return
        col_filial = self.combos_mapeamento.get('coluna_filial')
        if not col_filial or not col_filial.get():
            messagebox.showerror("Erro", "É obrigatório escolher a coluna da Filial.")
            return
        mapeamento = {'coluna_filial': col_filial.get()}
        for metrica in mod_metas.METRICAS_COM_META:
            valor = self.combos_mapeamento[metrica].get()
            if valor:
                mapeamento[metrica] = valor
        aba = getattr(self, '_aba_metas_atual', None) or mod_metas.listar_abas(caminho)[0]
        mod_metas.salvar_mapeamento(caminho, aba, mapeamento)
        self.lbl_status_metas.config(text=f"Mapeamento salvo: {os.path.basename(caminho)} (aba '{aba}')")
        messagebox.showinfo("Pronto", "Mapeamento de metas salvo. Ele será usado na próxima geração de relatórios.")

    # -------------------------------------------------------- Aba 3: Gerentes
    def _montar_aba_gerentes(self):
        f = self.aba_gerentes
        pad = {'padx': 8, 'pady': 6}

        ttk.Label(f, text=(
            "Cadastre um e-mail por FILIAL (prioridade) ou por REGIÃO (usado se a "
            "filial não tiver e-mail próprio, ou para o relatório consolidado da região)."
        ), wraplength=900, justify='left').pack(anchor='w', **pad)

        colunas = ('Sel', 'Regiao', 'Filial', 'Nome', 'Email')
        frame_tree = ttk.Frame(f)
        frame_tree.pack(fill='both', expand=True, padx=8, pady=6)
        self.tabela_gerentes = ttk.Treeview(frame_tree, columns=colunas, show='headings', height=16)
        self.tabela_gerentes.heading('Sel', text='✓')
        self.tabela_gerentes.column('Sel', width=32, anchor='center', stretch=False)
        for c in ('Regiao', 'Filial', 'Nome', 'Email'):
            self.tabela_gerentes.heading(c, text=c)
            self.tabela_gerentes.column(c, width=170)
        self.tabela_gerentes.bind('<Button-1>', self._alternar_selecao_gerente)
        scroll_tree = ttk.Scrollbar(frame_tree, orient='vertical', command=self.tabela_gerentes.yview)
        self.tabela_gerentes.configure(yscrollcommand=scroll_tree.set)
        self.tabela_gerentes.pack(side='left', fill='both', expand=True)
        scroll_tree.pack(side='right', fill='y')

        botoes = ttk.Frame(f)
        botoes.pack(fill='x', padx=8, pady=4)
        ttk.Button(botoes, text="Adicionar", command=self._adicionar_gerente).pack(side='left', padx=4)
        ttk.Button(botoes, text="Editar selecionado", command=self._editar_gerente).pack(side='left', padx=4)
        ttk.Button(botoes, text="Remover selecionado", command=self._remover_gerente).pack(side='left', padx=4)
        ttk.Button(botoes, text="Marcar todos",
                   command=lambda: self._marcar_todos_gerentes(True)).pack(side='left', padx=(20, 4))
        ttk.Button(botoes, text="Desmarcar todos",
                   command=lambda: self._marcar_todos_gerentes(False)).pack(side='left', padx=4)

        bloco_envio = ttk.LabelFrame(f, text="Enviar relatórios por e-mail")
        bloco_envio.pack(fill='x', padx=8, pady=(10, 6))

        linha_pasta = ttk.Frame(bloco_envio)
        linha_pasta.pack(fill='x', padx=8, pady=(8, 4))
        self.lbl_status_relatorios = ttk.Label(linha_pasta, text=self._texto_status_relatorios())
        self.lbl_status_relatorios.pack(side='left')
        ttk.Button(linha_pasta, text="Usar pasta de relatórios já gerados...",
                   command=self._selecionar_pasta_relatorios_existente).pack(side='left', padx=8)

        linha_envio = ttk.Frame(bloco_envio)
        linha_envio.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(linha_envio, text="Enviar para todos de uma vez",
                   command=lambda: self._abrir_janela_envio()).pack(side='left', padx=(0, 4))
        ttk.Button(linha_envio, text="Enviar para os marcados (✓)",
                   command=self._enviar_para_selecionados).pack(side='left', padx=4)

        self._carregar_tabela_gerentes()

    def _texto_status_relatorios(self):
        if not self.relatorios_gerados:
            return "Nenhum relatório carregado ainda (gere na aba 1, ou use uma pasta já gerada antes)."
        return f"{len(self.relatorios_gerados)} relatório(s) prontos para {self.mes_ano_texto}."

    def _atualizar_status_relatorios(self):
        self.lbl_status_relatorios.config(text=self._texto_status_relatorios())

    def _mes_ano_texto_da_pasta(self, pasta):
        """A pasta de saída é nomeada '<mês>-<abreviação>-<ano>' (ex:
        '08-ago-2026', ver `_gerar_relatorios`) — tenta recuperar esse
        período a partir do nome da pasta escolhida, pra usar no assunto
        do e-mail; se a pasta tiver sido renomeada, usa o nome dela
        mesmo, sem travar por causa disso."""
        nome = os.path.basename(os.path.normpath(pasta))
        m = re.match(r'^(\d{2})-[a-z]{3}-(\d{4})$', nome, re.IGNORECASE)
        if m:
            mes, ano = m.groups()
            return f"{mes}/{ano}"
        return nome

    def _selecionar_pasta_relatorios_existente(self):
        pasta = filedialog.askdirectory(
            title="Selecione a pasta de relatórios já gerados (ex: Relatórios/08-ago-2026)")
        if not pasta:
            return
        try:
            gerados = mod_relatorios.carregar_relatorios_gerados(pasta)
        except FileNotFoundError:
            messagebox.showerror(
                "Pasta não reconhecida",
                "Essa pasta não tem relatórios reconhecidos por este programa.\n\n"
                "Selecione a pasta exata que foi criada na aba 1 (ex: Relatórios/08-ago-2026) "
                "— tem que ser a pasta com os PDFs dentro, não uma pasta acima ou "
                "dentro dela.")
            return
        except Exception as e:
            messagebox.showerror("Erro", f"Não consegui ler os relatórios dessa pasta:\n{e}")
            return
        if not gerados:
            messagebox.showerror("Erro", "Não encontrei nenhum relatório válido nessa pasta "
                                          "(os arquivos podem ter sido movidos ou apagados).")
            return

        self.relatorios_gerados = gerados
        self.mes_ano_texto = self._mes_ano_texto_da_pasta(pasta)
        self.registros_atuais = []
        self.metas_por_filial = {}

        pares = sorted({(g['regiao'], g['filial']) for g in gerados if g['tipo'] == 'filial'})
        self.config_app['regioes_filiais'] = [list(p) for p in pares]
        mod_config.salvar(self.config_app)

        self._atualizar_status_relatorios()
        messagebox.showinfo("Pronto", f"{len(gerados)} relatório(s) carregados de:\n{pasta}")

    _MARCADO = '☑'
    _DESMARCADO = '☐'

    def _alternar_selecao_gerente(self, event):
        """Clicar na caixinha (coluna 'Sel') marca/desmarca aquela linha,
        pra poder escolher vários gerentes de uma vez antes de mandar
        "Enviar para os marcados"."""
        if self.tabela_gerentes.identify_region(event.x, event.y) != 'cell':
            return
        if self.tabela_gerentes.identify_column(event.x) != '#1':
            return
        item = self.tabela_gerentes.identify_row(event.y)
        if not item:
            return
        valores = list(self.tabela_gerentes.item(item, 'values'))
        valores[0] = self._DESMARCADO if valores[0] == self._MARCADO else self._MARCADO
        self.tabela_gerentes.item(item, values=valores)

    def _marcar_todos_gerentes(self, marcar):
        marca = self._MARCADO if marcar else self._DESMARCADO
        for item in self.tabela_gerentes.get_children():
            valores = list(self.tabela_gerentes.item(item, 'values'))
            valores[0] = marca
            self.tabela_gerentes.item(item, values=valores)

    def _enviar_para_selecionados(self):
        marcados = [item for item in self.tabela_gerentes.get_children()
                    if self.tabela_gerentes.item(item, 'values')[0] == self._MARCADO]
        if not marcados:
            messagebox.showinfo("Aviso", "Marque a caixinha (✓) de pelo menos um gerente na tabela "
                                          "pra enviar só pra eles.")
            return
        filtro = set()
        for item in marcados:
            _sel, regiao, filial, _nome, _email = self.tabela_gerentes.item(item, 'values')
            if filial:
                filtro.add(('filial', filial))
            elif regiao:
                filtro.add(('regiao', regiao))
        self._abrir_janela_envio(filtro_destinos=filtro)

    def _carregar_tabela_gerentes(self):
        for item in self.tabela_gerentes.get_children():
            self.tabela_gerentes.delete(item)
        for g in mod_emails.carregar_gerentes(EMAILS_CSV):
            self.tabela_gerentes.insert('', 'end', values=(self._DESMARCADO, g.get('Regiao', ''), g.get('Filial', ''),
                                                             g.get('Nome', ''), g.get('Email', '')))

    def _salvar_tabela_gerentes(self):
        gerentes = []
        for item in self.tabela_gerentes.get_children():
            _sel, regiao, filial, nome, email = self.tabela_gerentes.item(item, 'values')
            gerentes.append({'Regiao': regiao, 'Filial': filial, 'Nome': nome, 'Email': email})
        mod_emails.salvar_gerentes(EMAILS_CSV, gerentes)

    _FILIAL_TODAS = "(toda a região — sem filial específica)"

    def _opcoes_regioes(self):
        """Regiões conhecidas, a partir dos pares vistos na última geração
        de relatórios (salvos em config_app)."""
        pares = self.config_app.get('regioes_filiais') or []
        return sorted({r for r, _f in pares if r})

    def _opcoes_filiais_da_regiao(self, regiao):
        """Filiais conhecidas que pertencem a essa região (uma filial é
        sempre de uma região só — por isso a lista de filiais depende da
        região escolhida, não é uma lista solta)."""
        pares = self.config_app.get('regioes_filiais') or []
        return sorted({f for r, f in pares if r == regiao and f})

    def _janela_gerente(self, valores_iniciais=None, callback=None):
        janela = tk.Toplevel(self)
        janela.title("Gerente")
        janela.geometry("420x280")

        opcoes_regiao = self._opcoes_regioes()
        ttk.Label(janela, text="Região:").grid(row=0, column=0, sticky='w', padx=8, pady=6)
        var_regiao = tk.StringVar()
        combo_regiao = ttk.Combobox(janela, textvariable=var_regiao, values=opcoes_regiao,
                                     state='readonly' if opcoes_regiao else 'disabled', width=28)
        combo_regiao.grid(row=0, column=1, padx=8, pady=6)
        if not opcoes_regiao:
            ttk.Label(janela, text="(gere os relatórios na aba 1 primeiro pra carregar as opções)",
                      foreground='#9C6500', wraplength=250, justify='left').grid(
                row=1, column=0, columnspan=2, sticky='w', padx=8)

        ttk.Label(janela, text="Filial:").grid(row=2, column=0, sticky='w', padx=8, pady=6)
        var_filial = tk.StringVar()
        combo_filial = ttk.Combobox(janela, textvariable=var_filial, values=[], state='disabled', width=28)
        combo_filial.grid(row=2, column=1, padx=8, pady=6)
        ttk.Label(janela, text="(deixe em branco pra um gerente responsável pela região toda)",
                  foreground='#666666', wraplength=250, justify='left').grid(
            row=3, column=0, columnspan=2, sticky='w', padx=8)

        def _ao_mudar_regiao(event=None, manter_filial=None):
            filiais = self._opcoes_filiais_da_regiao(var_regiao.get())
            valores = [self._FILIAL_TODAS] + filiais
            combo_filial.config(values=valores, state='readonly' if filiais else 'disabled')
            if manter_filial in filiais:
                var_filial.set(manter_filial)
            else:
                var_filial.set(self._FILIAL_TODAS)

        combo_regiao.bind('<<ComboboxSelected>>', lambda e: _ao_mudar_regiao())

        if valores_iniciais:
            regiao_ini, filial_ini = valores_iniciais[0], valores_iniciais[1]
            if regiao_ini:
                var_regiao.set(regiao_ini)
                _ao_mudar_regiao(manter_filial=filial_ini)

        campos = {}
        for i, campo in enumerate(('Nome', 'Email'), start=4):
            ttk.Label(janela, text=campo + ":").grid(row=i, column=0, sticky='w', padx=8, pady=6)
            valor_inicial = (valores_iniciais[2] if campo == 'Nome' else valores_iniciais[3]) if valores_iniciais else ''
            var = tk.StringVar(value=valor_inicial)
            ttk.Entry(janela, textvariable=var, width=32).grid(row=i, column=1, padx=8, pady=6)
            campos[campo] = var

        def confirmar():
            regiao = var_regiao.get().strip()
            filial_sel = var_filial.get().strip()
            filial = '' if filial_sel in ('', self._FILIAL_TODAS) else filial_sel
            nome = campos['Nome'].get().strip()
            email = campos['Email'].get().strip()
            if not email:
                messagebox.showerror("Erro", "Informe pelo menos o e-mail.", parent=janela)
                return
            if '@' not in email or '.' not in email.split('@')[-1]:
                messagebox.showerror("Erro", "Esse e-mail não parece válido. Confira e tente de novo.", parent=janela)
                return
            if not regiao:
                messagebox.showerror("Erro", "Escolha a Região desse gerente.", parent=janela)
                return
            callback((regiao, filial, nome, email))
            janela.destroy()

        ttk.Button(janela, text="Salvar", command=confirmar).grid(row=6, column=0, columnspan=2, pady=12)

    def _adicionar_gerente(self):
        def salvar(valores):
            self.tabela_gerentes.insert('', 'end', values=(self._DESMARCADO,) + tuple(valores))
            self._salvar_tabela_gerentes()
        self._janela_gerente(callback=salvar)

    def _editar_gerente(self):
        sel = self.tabela_gerentes.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione uma linha pra editar.")
            return
        item = sel[0]
        marca_atual, *valores_atuais = self.tabela_gerentes.item(item, 'values')

        def salvar(valores):
            self.tabela_gerentes.item(item, values=(marca_atual,) + tuple(valores))
            self._salvar_tabela_gerentes()
        self._janela_gerente(valores_iniciais=valores_atuais, callback=salvar)

    def _remover_gerente(self):
        sel = self.tabela_gerentes.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione uma linha pra remover.")
            return
        for item in sel:
            self.tabela_gerentes.delete(item)
        self._salvar_tabela_gerentes()

    # --------------------------------------------------- Aba 4: Config e-mail
    def _montar_aba_email_config(self):
        f = self.aba_email_config
        pad = {'padx': 8, 'pady': 8}

        ttk.Label(f, text=(
            "Use uma SENHA DE APP do Gmail, não a senha normal da conta.\n"
            "Como gerar: entre na Conta Google -> Segurança -> Verificação em duas etapas "
            "(precisa estar ativada) -> Senhas de app -> crie uma senha para 'E-mail'."
        ), justify='left', wraplength=900).pack(anchor='w', **pad)

        bloco = ttk.Frame(f)
        bloco.pack(anchor='w', **pad)
        ttk.Label(bloco, text="E-mail Gmail do remetente:").grid(row=0, column=0, sticky='w', pady=4)
        self.var_gmail_remetente = tk.StringVar(value=self.config_app.get('gmail_remetente', ''))
        ttk.Entry(bloco, textvariable=self.var_gmail_remetente, width=40).grid(row=0, column=1, pady=4)

        ttk.Label(bloco, text="Senha de app (16 dígitos):").grid(row=1, column=0, sticky='w', pady=4)
        self.var_gmail_senha = tk.StringVar(value=self.config_app.get('gmail_senha_app', ''))
        ttk.Entry(bloco, textvariable=self.var_gmail_senha, width=40, show='•').grid(row=1, column=1, pady=4)

        botoes = ttk.Frame(f)
        botoes.pack(anchor='w', **pad)
        ttk.Button(botoes, text="Salvar", command=self._salvar_config_email).pack(side='left', padx=4)
        self.btn_testar_conexao = ttk.Button(botoes, text="Testar conexão", command=self._testar_conexao_email)
        self.btn_testar_conexao.pack(side='left', padx=4)

        self.lbl_status_email = ttk.Label(f, text="")
        self.lbl_status_email.pack(anchor='w', padx=8)

        ttk.Label(f, text=(
            "Aviso: essas informações ficam salvas em texto simples em "
            "data/config.json, dentro da pasta do programa. Não compartilhe essa pasta."
        ), foreground='#9C6500', wraplength=900, justify='left').pack(anchor='w', padx=8, pady=(20, 8))

    def _salvar_config_email(self):
        remetente = self.var_gmail_remetente.get().strip()
        senha = self.var_gmail_senha.get().strip()
        if remetente and '@' not in remetente:
            messagebox.showerror("Erro", "Esse e-mail não parece válido.")
            return
        self.config_app['gmail_remetente'] = remetente
        self.config_app['gmail_senha_app'] = senha
        mod_config.salvar(self.config_app)
        self.lbl_status_email.config(text="Configuração salva.")

    def _testar_conexao_email(self):
        remetente = self.var_gmail_remetente.get().strip()
        senha = self.var_gmail_senha.get().strip()
        if not remetente or not senha:
            messagebox.showerror("Erro", "Preencha o e-mail e a senha de app primeiro.")
            return
        if '@' not in remetente:
            messagebox.showerror("Erro", "Esse e-mail não parece válido.")
            return
        self.lbl_status_email.config(text="Testando...")

        def trabalho():
            ok, msg = mod_emails.testar_conexao(remetente, senha)
            self.after(0, lambda: self.lbl_status_email.config(text=msg))
            if not ok:
                self.after(0, lambda: messagebox.showerror("Falha na conexão", msg))

        self._executar_em_thread(trabalho, botoes=[self.btn_testar_conexao])

    # ------------------------------------------------------- Janela de envio
    def _abrir_janela_envio(self, filtro_destinos=None):
        if not self.relatorios_gerados:
            messagebox.showinfo("Aviso", "Gere os relatórios primeiro, na aba 1.")
            return
        remetente = self.config_app.get('gmail_remetente')
        senha = self.config_app.get('gmail_senha_app')
        if not remetente or not senha:
            messagebox.showerror("Erro", "Configure o e-mail remetente na aba 4 antes de enviar.")
            return

        if filtro_destinos is not None:
            def _chave(item):
                return (item['tipo'], item['filial'] if item['tipo'] == 'filial' else item['regiao'])
            qtd = sum(1 for item in self.relatorios_gerados
                      if item['tipo'] in ('filial', 'regiao') and _chave(item) in filtro_destinos)
            texto_qtd = f"{qtd} relatório(s) selecionado(s), para {self.mes_ano_texto}."
        else:
            texto_qtd = f"{len(self.relatorios_gerados)} relatórios prontos para {self.mes_ano_texto}."

        janela = tk.Toplevel(self)
        janela.title("Enviar relatórios por e-mail")
        janela.geometry("640x520")

        ttk.Label(janela, text=texto_qtd, font=('Arial', 11, 'bold')).pack(anchor='w', padx=10, pady=8)

        ttk.Label(janela, text=(
            "Sem \"Modo teste\", cada relatório vai automaticamente pro e-mail já "
            "cadastrado do gerente correspondente (aba 3) — não precisa digitar nada."
        ), foreground='#666666', wraplength=600, justify='left').pack(anchor='w', padx=10)

        var_teste = tk.BooleanVar(value=True)
        chk = ttk.Checkbutton(janela, text="Modo teste: mandar tudo pra um único e-mail antes de enviar de verdade",
                               variable=var_teste)
        chk.pack(anchor='w', padx=10, pady=(4, 0))

        frame_teste = ttk.Frame(janela)
        frame_teste.pack(anchor='w', padx=10, pady=4)
        lbl_email_teste = ttk.Label(frame_teste, text="E-mail de teste:")
        lbl_email_teste.pack(side='left')
        var_email_teste = tk.StringVar(value=remetente)
        entry_email_teste = ttk.Entry(frame_teste, textvariable=var_email_teste, width=35)
        entry_email_teste.pack(side='left', padx=6)

        def _atualizar_estado_campo_teste(*_args):
            estado = 'normal' if var_teste.get() else 'disabled'
            entry_email_teste.config(state=estado)
            lbl_email_teste.config(foreground='' if var_teste.get() else '#999999')

        var_teste.trace_add('write', _atualizar_estado_campo_teste)
        _atualizar_estado_campo_teste()

        progress_envio = ttk.Progressbar(janela, mode='indeterminate')
        progress_envio.pack(fill='x', padx=10, pady=(4, 0))

        frame_resultado = ttk.Frame(janela)
        frame_resultado.pack(fill='both', expand=True, padx=10, pady=8)
        txt_resultado = tk.Text(frame_resultado, height=16, wrap='word')
        scroll_resultado = ttk.Scrollbar(frame_resultado, orient='vertical', command=txt_resultado.yview)
        txt_resultado.configure(yscrollcommand=scroll_resultado.set)
        txt_resultado.pack(side='left', fill='both', expand=True)
        scroll_resultado.pack(side='right', fill='y')

        evento_cancelar = threading.Event()

        def enviar():
            gerentes = mod_emails.carregar_gerentes(EMAILS_CSV)
            email_teste = var_email_teste.get().strip() if var_teste.get() else None
            if var_teste.get() and not email_teste:
                messagebox.showerror("Erro", "Informe o e-mail de teste.", parent=janela)
                return
            if not var_teste.get():
                confirmar = messagebox.askyesno(
                    "Confirmar envio",
                    "Isso vai mandar cada relatório para o e-mail cadastrado do gerente "
                    "correspondente, de verdade. Confirmar?", parent=janela)
                if not confirmar:
                    return

            txt_resultado.delete('1.0', 'end')
            evento_cancelar.clear()
            btn_cancelar.config(state='normal')

            def trabalho():
                resultados = mod_emails.enviar_relatorios_gerados(
                    remetente, senha, gerentes, self.relatorios_gerados, self.mes_ano_texto,
                    progresso=lambda m: self.after(0, lambda m=m: txt_resultado.insert('end', m + "\n")),
                    modo_teste_email=email_teste, cancelar=evento_cancelar, filtro_destinos=filtro_destinos)
                enviados = sum(1 for r in resultados if r['status'] == 'enviado')
                pulados = sum(1 for r in resultados if r['status'] == 'pulado')
                erros = sum(1 for r in resultados if r['status'] == 'erro')
                resumo = f"\nResumo: {enviados} enviados, {pulados} sem e-mail cadastrado, {erros} com erro."
                if evento_cancelar.is_set():
                    resumo += " (cancelado pelo usuário — o restante não foi enviado)"
                resumo += "\n"
                self.after(0, lambda: txt_resultado.insert('end', resumo))
                self.after(0, lambda: btn_cancelar.config(state='disabled'))

            self._executar_em_thread(trabalho, botoes=[btn_enviar_real], progresso=progress_envio)

        def cancelar():
            evento_cancelar.set()
            btn_cancelar.config(state='disabled')
            txt_resultado.insert('end', "\nCancelando... (termina de enviar o relatório que já estiver em andamento)\n")

        frame_botoes_envio = ttk.Frame(janela)
        frame_botoes_envio.pack(pady=6)
        btn_enviar_real = ttk.Button(frame_botoes_envio, text="Enviar agora", command=enviar)
        btn_enviar_real.pack(side='left', padx=4)
        btn_cancelar = ttk.Button(frame_botoes_envio, text="Cancelar", command=cancelar, state='disabled')
        btn_cancelar.pack(side='left', padx=4)


if __name__ == '__main__':
    bootstrap_dados_iniciais()
    app = App()
    app.mainloop()
