@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
echo ============================================
echo   Relatorios Comerciais - Instalacao (rodar 1x)
echo ============================================
echo.
echo Procurando o Python neste computador...

set "PY=py -3"
%PY% -c "pass" >nul 2>&1
if not errorlevel 1 goto :python_ok

set "PY=python"
%PY% -c "pass" >nul 2>&1
if not errorlevel 1 goto :python_ok

if not exist "%LocalAppData%\Programs\Python\Launcher\py.exe" goto :sem_python
set PY="%LocalAppData%\Programs\Python\Launcher\py.exe" -3
%PY% -c "pass" >nul 2>&1
if not errorlevel 1 goto :python_ok

:sem_python
echo.
echo [ERRO] O Python nao foi encontrado neste computador.
echo.
echo Baixe e instale em: https://www.python.org/downloads/
echo IMPORTANTE: na tela de instalacao, marque a caixinha
echo "Add Python to PATH" antes de clicar em Instalar.
echo.
echo Se voce ja instalou o Python e mesmo assim ve esta mensagem, o
echo Windows pode estar abrindo a Loja (Microsoft Store) no lugar do
echo Python de verdade. Para corrigir isso: abra Configuracoes do
echo Windows -^> Aplicativos -^> Configuracoes avancadas do aplicativo
echo -^> Aliases de execucao do aplicativo -^> desligue "python.exe" e
echo "python3.exe".
echo.
echo Depois de resolver, feche esta janela e clique de novo neste
echo arquivo "1_Instalar.bat".
echo.
pause
exit /b 1

:python_ok
echo Python encontrado. Verificando o modulo de interface grafica (tkinter)...
%PY% -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERRO] Esse Python nao tem o modulo "tkinter" instalado.
    echo Isso acontece quando, na instalacao do Python, a opcao
    echo "tcl/tk and IDLE" foi desmarcada. Reinstale o Python marcando
    echo essa opcao ^(ela vem marcada por padrao^).
    echo.
    pause
    exit /b 1
)

echo Tudo certo. Instalando as bibliotecas necessarias...
%PY% -m pip install --upgrade pip >nul
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERRO] Algo deu errado instalando as bibliotecas. Copie o
    echo texto acima e mande para quem preparou o programa.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Tudo pronto!
echo   Agora e so clicar duas vezes em:
echo   "2_Abrir Relatorios Comerciais.bat"
echo ============================================
pause
