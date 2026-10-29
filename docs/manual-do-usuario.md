# Relatórios Comerciais

Programa local para gerar e enviar os relatórios mensais de resultado
comercial da empresa (por região e por filial), a partir do arquivo
mensal que a diretoria já produz hoje. Os relatórios saem em **PDF**
(não editável), organizados em uma subpasta por região, e vêm
acompanhados de um dashboard geral com gráficos.

**Tudo roda no seu computador.** Os dados financeiros nunca são
enviados para nenhum servidor — nem nuvem, nem IA, nada. A única coisa
que sai do computador é o e-mail que você mesmo decide mandar, na aba
"3. E-mails dos Gerentes".

---

## 1. Instalação (só precisa fazer uma vez) — modo mais simples

Não precisa de VSCode nem de nenhum editor de código. Só precisa do
**Python**, que é gratuito e instala como qualquer outro programa:

1. Baixe em https://www.python.org/downloads/ e instale.
   **Importante:** na primeira tela do instalador, marque a caixinha
   **"Add Python to PATH"** antes de clicar em "Install Now".

2. Descompacte esta pasta (RelatoriosComerciais) em algum lugar fixo do
   computador, tipo a Área de Trabalho ou "Meus Documentos".

3. Clique duas vezes em **`1_Instalar.bat`**. Ele confere se o Python
   está certo e instala as bibliotecas que o programa usa (openpyxl pra
   ler as planilhas, reportlab e matplotlib pra gerar os PDFs e os
   gráficos). Só precisa fazer isso uma vez.

4. Pronto! Daqui pra frente, **é só clicar duas vezes em
   `2_Abrir Relatorios Comerciais.bat`** sempre que quiser usar o programa.
   Pode arrastar esse arquivo pra Área de Trabalho e criar um atalho,
   fica igual abrir qualquer outro programa.

### Opcional — gerar um .exe "de verdade" (sem precisar do Python depois)

Se quiser um único arquivo `.exe` que funcione em qualquer computador
Windows, mesmo sem Python instalado nele:

1. Depois de rodar o `1_Instalar.bat` uma vez (precisa do Python só
   pra esse passo), clique duas vezes em
   **`3_Gerar_Executavel_Opcional.bat`**.
2. Vai demorar alguns minutos (o matplotlib deixa esse passo mais lento
   e o `.exe` final mais pesado do que antes) e vai criar a pasta
   `dist`, com o arquivo `RelatoriosComerciais.exe` dentro.
3. Copie a pasta `dist` inteira (o `.exe` sozinho, sem a pasta `data`
   ao lado, ainda funciona, mas cria uma pasta `data` nova no primeiro
   uso) para onde quiser — inclusive para outro computador Windows sem
   Python instalado. Daí em diante é só clicar duas vezes nesse `.exe`.

---

## 2. Como usar todo mês

### Passo 1 — Gerar os relatórios (aba "1. Gerar Relatórios")
1. Selecione o arquivo `.xlsm` mensal que a diretoria manda (o mesmo
   arquivo com a aba "Dados").
2. Escolha o mês e o ano.
3. Escolha a pasta onde salvar (o programa cria uma subpasta com o
   mês/ano automaticamente).
4. Clique em **"Gerar relatórios (região + filial)"**.
5. O programa gera, dentro de `Relatórios/<mês>-<abreviação>-<ano>/` (ex:
   `Relatórios/08-ago-2026/`):
   - uma **subpasta por região** (ex: `Nordeste/`), com 1 PDF da região
     (`Monitor_Comercio_<Região>.pdf`) e 1 PDF por filial dessa região
     (`Monitor_FCA_<Filial>.pdf`) — mesmo formato que a diretoria já usa
     hoje, só que agora em PDF (não editável) em vez de planilha;
   - um **dashboard geral** (`00_Dashboard_Geral.pdf`) solto na raiz da
     pasta, com uma tabela resumo de todas as regiões e gráficos
     (faturamento e lucro por região, %lucro por filial do melhor pro
     pior, inadimplência por região) — pra ter uma visão rápida do mês
     inteiro, sem precisar abrir arquivo por arquivo.

   No relatório de cada filial, as 3 linhas (Região / Filial / Total
   Geral) mostram números diferentes entre si: a linha da Região é o
   subtotal de verdade da região, e "Total Geral" é a soma de toda a
   empresa — não é mais a mesma linha repetida 3 vezes.

### Passo 2 — Configurar as metas (aba "2. Metas por Filial")
Isso é **opcional**, mas deixa as cores dos relatórios muito mais úteis
(comparando a loja com a meta dela, não só verde/vermelho por lucro).

1. Selecione o arquivo de metas por loja (o documento que vocês já
   usam hoje).
2. Clique em **"Carregar colunas"** — o programa lê os nomes das
   colunas desse arquivo.
3. Escolha, nos menus, **qual coluna do arquivo de metas corresponde a
   qual métrica do relatório** (ex: a coluna "Meta Faturamento" do
   arquivo deles vira a métrica "Vlr Faturamento" do relatório). Você
   só precisa preencher as métricas que realmente têm meta — pode
   deixar em branco o resto.
4. Clique em **"Salvar mapeamento"**.

**Se no mês seguinte a planilha de metas vier com colunas diferentes
(nomes novos, ordem diferente, etc.), é só repetir esses 4 passos com
o arquivo novo** — não precisa mexer em nada no código. O programa vai
usar automaticamente o mapeamento mais recente salvo.

Um modelo de exemplo está em `data/metas_modelo_exemplo.xlsx`, só pra
referência de como uma planilha de metas poderia ser — não precisa
usar esse formato exato, o mapeamento se adapta a qualquer estrutura.

### Passo 3 — Cadastrar os e-mails dos gerentes (aba "3. E-mails dos Gerentes")
Cadastre um e-mail por filial (prioridade) e/ou por região (usado no
relatório consolidado da região, ou como reserva se a filial não tiver
e-mail próprio cadastrado). Isso fica salvo — só precisa cadastrar uma
vez e ir atualizando quando alguém mudar.

Ao adicionar ou editar um gerente, a Região e a Filial não são mais
digitadas à mão: primeiro você escolhe a Região numa lista (montada a
partir da última planilha processada na aba 1), e a Filial mostra só
as filiais daquela região (já que uma filial pertence a uma região).
Deixe a Filial em branco pra cadastrar um gerente responsável pela
região toda (recebe o relatório consolidado da região). Se a lista de
Região aparecer vazia, gere os relatórios na aba 1 pelo menos uma vez
antes de cadastrar gerentes.

É nesta aba também que fica o envio por e-mail (ver Passo 5), depois
que os relatórios já tiverem sido gerados na aba 1.

### Passo 4 — Configurar o e-mail de envio (aba "4. Config. de E-mail")
1. Digite o Gmail que vai mandar os relatórios.
2. Digite uma **Senha de App** do Gmail (não a senha normal da conta —
   veja como gerar abaixo).
3. Clique em "Salvar" e depois em "Testar conexão" pra confirmar que
   está tudo certo.

**Como gerar uma Senha de App no Gmail:**
1. Entre em https://myaccount.google.com/security
2. Ative a **Verificação em duas etapas**, se ainda não estiver ativa
   (é obrigatório pra gerar senha de app).
3. Procure por **"Senhas de app"** (ou acesse
   https://myaccount.google.com/apppasswords).
4. Crie uma senha para "E-mail" / "Outro (nome personalizado)" — vai
   gerar um código de 16 letras. Cole esse código no programa.
5. Se um dia quiser cortar o acesso do programa, é só revogar essa
   senha de app na mesma tela do Google, sem mexer na senha principal
   da conta.

### Passo 5 — Enviar (aba "3. E-mails dos Gerentes")
Depois de gerar os relatórios na aba 1, volte pra aba 3.

**Se você fechou o programa e abriu de novo** (ou trocou de mês sem
querer), não precisa gerar tudo outra vez: clique em **"Usar pasta de
relatórios já gerados..."** e selecione a pasta do mês desejado (ex:
`Relatórios/08-ago-2026`) — o programa reconhece os relatórios que já estavam
lá (cada geração salva um arquivo `_relatorios.json` dentro da própria
pasta, com a lista do que foi gerado) e a tela volta a mostrar quantos
relatórios estão prontos, exatamente como se tivessem acabado de ser
gerados.

Depois, escolha um dos dois botões:
- **"Enviar para todos de uma vez"** — manda pra todo mundo cadastrado,
  cada gerente recebendo só o relatório da própria filial/região.
- **"Enviar para os marcados (✓)"** — marque a caixinha na primeira
  coluna da tabela (clique pra marcar/desmarcar) de um ou mais
  gerentes, e manda só pra eles. Os botões "Marcar todos" e "Desmarcar
  todos" ajudam quando quiser marcar quase todo mundo, ou começar de
  novo. Útil pra reenviar pra alguns gerentes sem mexer no que já foi
  mandado pros outros.

Recomendo sempre deixar o **"Modo teste"** marcado na primeira vez do
mês — assim todos os relatórios vão pro seu próprio e-mail antes,
pra você conferir se está tudo certo, e só depois desmarcar e mandar
de verdade pros gerentes. Durante o envio, o botão **"Cancelar"** para
o restante da fila (os que já foram enviados não são desfeitos).
O dashboard geral (`00_Dashboard_Geral.pdf`) não é mandado
automaticamente pra ninguém — fica salvo na pasta de saída pra você
anexar manualmente se quiser.

---

## 3. Onde ficam os dados salvos

Tudo fica dentro da pasta do programa, na subpasta
`Arquivos do Programa (não mexer)/`:
- `.../emails_gerentes.csv` — cadastro de e-mails
- `.../config.json` — e-mail/senha de app do Gmail, últimos caminhos usados
- `.../metas_mapeamento.json` — o mapeamento de colunas da planilha de metas
- `.../erro.log` — só aparece se algo inesperado der errado; guarda o
  detalhe técnico do erro pra quem for te ajudar a resolver (nunca
  contém dados financeiros, só a mensagem do erro em si)

**Atenção:** `config.json` guarda a senha de app do Gmail em texto
simples. Não compartilhe essa pasta nem suba ela pra nenhum lugar (nuvem,
pendrive de terceiros, etc.). Se precisar mandar o programa pra outra
pessoa, apague esse arquivo antes (ou simplesmente não copie a pasta
`Arquivos do Programa (não mexer)/` — o programa cria uma nova, vazia,
sozinho).

Os relatórios gerados ficam em `Relatórios/<mês>-<abreviação>-<ano>/`
(ou na pasta que você escolher na aba 1), organizados assim:

```
Relatórios/08-ago-2026/
├── _relatorios.json         <- lista do que foi gerado (usado por "Usar pasta já gerada...")
├── 00_Dashboard_Geral.pdf
├── Nordeste/
│   ├── Monitor_Comercio_Nordeste.pdf
│   ├── Monitor_FCA_Bahia.pdf
│   └── Monitor_FCA_Recife.pdf
├── Sudeste/
│   ├── Monitor_Comercio_Sudeste.pdf
│   └── ...
└── ...
```

O `_relatorios.json` é só uma lista técnica (não tem dados financeiros,
só nomes de arquivo) — não precisa mexer nele, mas não apague, é ele
que permite carregar essa pasta de volta na aba 3 depois de fechar o
programa.

---

## 4. Estrutura do projeto (caso precise dar manutenção)

```
RelatoriosComerciais/
├── main.py                    -> interface gráfica (Tkinter)
├── core/
│   ├── dados.py                -> lê o arquivo mensal da diretoria
│   ├── metricas.py             -> calcula Vlr Faturamento, %Margem, %Lucro, etc.
│   ├── relatorios.py           -> gera os .pdf por região, por filial e o dashboard geral, com as cores
│   ├── metas.py                 -> lê a planilha de metas com mapeamento flexível de colunas
│   ├── emails.py                -> cadastro de gerentes + envio via Gmail (com cancelamento e filtro)
│   ├── config.py                -> salva/carrega configurações locais
│   └── appdir.py                -> descobre onde salvar dados persistentes (script ou .exe)
├── tests/                      -> testes automatizados (ver seção 5)
├── data/                        -> modelo de exemplo versionado (metas_modelo_exemplo.xlsx)
├── Arquivos do Programa (não mexer)/ -> cadastros/configs locais (criada sozinha, não sobe pro git)
├── exemplo_dados/               -> dados fictícios pra testar o programa sem arriscar dados reais
├── Relatórios/                  -> relatórios gerados (uma subpasta por região + dashboard geral)
├── requirements.txt              -> dependências pra rodar o programa (openpyxl, reportlab, matplotlib)
└── requirements-dev.txt          -> requirements.txt + pytest e pypdf, só pra quem for mexer no código
```

Se o arquivo mensal da diretoria mudar de nome de coluna no futuro
(muito raro, mas pode acontecer), ajuste o dicionário `RAW_FIELDS` em
`core/dados.py`. As fórmulas de cálculo (`core/metricas.py`) foram
conferidas célula a célula contra um relatório real antes de este
programa ser criado, e estão travadas por testes automatizados (ver
abaixo) — qualquer alteração nelas que mude um resultado precisa
quebrar um teste conscientemente, não passar despercebida.

O arquivo `exemplo_dados/dados_exemplo.xlsx` tem dados **fictícios**
(inventados, não são números reais de nenhuma empresa) só pra você experimentar
o programa sem usar uma planilha real — selecione ele na aba "1. Gerar
Relatórios" com mês "Agosto" e ano "2026" pra ver o fluxo completo
funcionando.

---

## 5. Testes automatizados (pra quem for mexer no código)

O `core/` (cálculo de métricas, leitura de dados, mapeamento de metas,
geração dos relatórios, envio de e-mail) e a interface (`main.py`) têm
testes automatizados em `tests/`. Rode antes de mexer em qualquer coisa,
e de novo depois, pra garantir que nada quebrou:

```
py -m pip install -r requirements-dev.txt
py -m pytest tests/
```

Isso não manda nenhum e-mail real nem depende de nenhum arquivo seu —
os testes criam seus próprios arquivos temporários de exemplo. Se
algum teste falhar depois de uma alteração em `core/metricas.py`,
pare e confira se o resultado novo está mesmo certo antes de ajustar o
teste — é exatamente esse o alarme que ele existe pra dar.

---

## 6. Solução de problemas

**"O Python não foi encontrado" mesmo já tendo instalado o Python**
Em alguns computadores, o Windows abre a Microsoft Store no lugar do
Python de verdade quando algum programa tenta chamar `python` pelo
nome. Para desligar isso: Configurações do Windows → Aplicativos →
Configurações avançadas do aplicativo → Aliases de execução do
aplicativo → desligue "python.exe" e "python3.exe". Os arquivos
`.bat` deste programa já tentam contornar esse problema sozinhos (via
o "Python Launcher", `py`), mas se mesmo assim continuar sem achar o
Python, esse é o primeiro lugar pra checar.

**A janela abre pequena demais ou com letra borrada**
Isso deveria estar corrigido (o programa avisa o Windows que sabe lidar
com telas de alta resolução), mas se ainda acontecer, tente: botão
direito no atalho do programa → Propriedades → Compatibilidade →
Alterar configurações de PPP altos → deixe o Windows ou o próprio
programa (não o "sistema") controlar o dimensionamento.

**"Não encontrei nenhum registro de Comércio para tal mês/ano"**
Confira se o mês e o ano selecionados na tela batem com os dados que
existem na aba "Dados" do arquivo (a coluna `mes` é numérica, 1 a 12,
e `unidade` precisa estar escrito exatamente "Comércio"). Se a aba
"Dados" tiver mudado de nome de coluna, o programa avisa exatamente
qual coluna está faltando.

**Cliquei duas vezes e não abriu nada**
Rode primeiro o `1_Instalar.bat` — ele confere o Python e as
bibliotecas e explica o que fazer se algo estiver faltando. Se depois
disso o `2_Abrir Relatorios Comerciais.bat` ainda não abrir nada, procure
o arquivo `Arquivos do Programa (não mexer)/erro.log` — qualquer erro
inesperado é registrado lá com detalhes técnicos.
