@echo off
cd /d "%~dp0"

set "PY=py -3"
set "PYW=pyw -3"
%PY% -c "pass" >nul 2>&1
if not errorlevel 1 goto :achou

set "PY=python"
set "PYW=pythonw"
%PY% -c "pass" >nul 2>&1
if not errorlevel 1 goto :achou

if not exist "%LocalAppData%\Programs\Python\Launcher\py.exe" goto :sem_python
set PY="%LocalAppData%\Programs\Python\Launcher\py.exe" -3
set PYW="%LocalAppData%\Programs\Python\Launcher\pyw.exe" -3
%PY% -c "pass" >nul 2>&1
if not errorlevel 1 goto :achou
goto :sem_python

:achou
%PY% -c "import tkinter, openpyxl" >nul 2>&1
if errorlevel 1 goto :falta_instalar
start "" %PYW% main.py
exit /b 0

:sem_python
chcp 65001 >nul 2>&1
echo ============================================
echo   Relatorios Comerciais - Python nao encontrado
echo ============================================
echo.
echo Rode primeiro o arquivo "1_Instalar.bat" (nesta mesma pasta) e
echo siga as instrucoes na tela.
echo.
pause
exit /b 1

:falta_instalar
chcp 65001 >nul 2>&1
echo ============================================
echo   Relatorios Comerciais - falta instalar
echo ============================================
echo.
echo Ainda falta preparar o programa neste computador. Rode o arquivo
echo "1_Instalar.bat" (nesta mesma pasta) uma vez e depois tente abrir
echo de novo.
echo.
pause
exit /b 1
