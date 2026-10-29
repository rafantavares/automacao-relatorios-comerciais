@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
echo ================================================================
echo   Relatorios Comerciais - Gerar arquivo .exe (opcional, rodar 1x)
echo ================================================================
echo.
echo Isso cria um arquivo RelatoriosComerciais.exe que roda em qualquer
echo computador Windows SEM precisar ter Python instalado.
echo.
echo Este computador (o que esta rodando este arquivo agora) precisa
echo ter o Python instalado so para CRIAR o .exe. Depois de criado,
echo o .exe pode ser copiado para qualquer outro computador Windows.
echo.

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
echo [ERRO] Python nao encontrado. Rode primeiro o "1_Instalar.bat".
pause
exit /b 1

:python_ok
echo Instalando o PyInstaller...
%PY% -m pip install --upgrade pyinstaller >nul
if errorlevel 1 (
    echo.
    echo [ERRO] Nao consegui instalar o PyInstaller. Copie o texto
    echo acima e mande para quem preparou o programa.
    pause
    exit /b 1
)

echo.
echo Gerando o executavel (isso pode demorar 1-2 minutos)...
%PY% -m PyInstaller --onefile --windowed --name "RelatoriosComerciais" ^
    --add-data "data;data" ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERRO] Algo deu errado ao gerar o executavel. Copie o texto
    echo acima e mande para quem preparou o programa.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo   Pronto! O arquivo executavel esta em:
echo   dist\RelatoriosComerciais.exe
echo.
echo   Copie a pasta "dist" inteira (ou so o .exe) para onde quiser -
echo   ele funciona sozinho, sem precisar do Python instalado. Na
echo   primeira vez que abrir em cada pasta/computador, ele cria uma
echo   pasta "Arquivos do Programa (nao mexer)" do lado dele sozinho.
echo ================================================================
pause
