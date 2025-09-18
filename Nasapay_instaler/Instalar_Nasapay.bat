@echo off
setlocal ENABLEDELAYEDEXPANSION

:: ============================================================
::  Instalar_Nasapay.bat  —  instalador simples por ZIP + 1 clique
::  - Requer: Nasapay.exe no MESMO diretório deste .bat
::  - Opcional: logo_boleto.png e logo_nasapay.png ao lado do .bat
:: ============================================================

:: ---------------- Elevar para Administrador (UAC) ----------------
>nul 2>&1 net session
if %errorlevel% neq 0 (
  echo Solicitando permissao de administrador...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

:: ---------------- Variaveis ----------------
set "SRC=%~dp0"
set "TARGET=C:\nasapay"
set "EXE=Nasapay.exe"
set "LOGO_BOLETO=logo_boleto.png"
set "LOGO_NASAPAY=logo_nasapay.png"
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Nasapay"
set "DESKTOP_COMMON=%Public%\Desktop"

echo.
echo ===============================================
echo   Instalando Nasapay em "%TARGET%"
echo ===============================================
echo.

:: ---------------- Preparar pasta base ----------------
if not exist "%TARGET%" (
  echo Criando pasta base: %TARGET%
  mkdir "%TARGET%" >nul 2>&1
) else (
  echo Pasta base ja existe: %TARGET%
)

:: ---------------- Criar SUBPASTAS padrao ----------------
for %%D in ("Arquivos" "Remessa" "Retorno" "Boletos") do (
  if not exist "%TARGET%\%%~D" (
    echo Criando pasta: %TARGET%\%%~D
    mkdir "%TARGET%\%%~D" >nul 2>&1
  ) else (
    echo Pasta ja existe: %TARGET%\%%~D
  )
)

:: ---------------- Limpeza de DADOS p/ iniciar do zero ----------------
echo.
echo Limpando dados anteriores (se existirem)...
del /q "%TARGET%\config.json"        2>nul
del /q "%TARGET%\*.db"               2>nul
del /q "%TARGET%\*.sqlite"           2>nul
del /q "%TARGET%\startup_log.txt"    2>nul
del /q "%TARGET%\*.log"              2>nul
del /q "%TARGET%\Boletos\*.*"        2>nul
del /q "%TARGET%\Arquivos\*.*"       2>nul
del /q "%TARGET%\Remessa\*.*"        2>nul
del /q "%TARGET%\Retorno\*.*"        2>nul
if exist "%TARGET%\boletos"  rmdir /s /q "%TARGET%\boletos"
if exist "%TARGET%\arquivos" rmdir /s /q "%TARGET%\arquivos"

:: ---------------- Copiar aplicativo e logos ----------------
echo.
if not exist "%SRC%%EXE%" (
  echo [ERRO] Nao encontrei "%EXE%" ao lado deste .bat.
  echo        Coloque o Nasapay.exe na mesma pasta do Instalar_Nasapay.bat e rode de novo.
  pause
  exit /b 1
)

echo Copiando executavel...
copy /y "%SRC%%EXE%" "%TARGET%\%EXE%" >nul

if exist "%SRC%%LOGO_BOLETO%" (
  echo Copiando logo do boleto...
  copy /y "%SRC%%LOGO_BOLETO%" "%TARGET%\%LOGO_BOLETO%" >nul
)

if exist "%SRC%%LOGO_NASAPAY%" (
  echo Copiando logo da aplicacao...
  copy /y "%SRC%%LOGO_NASAPAY%" "%TARGET%\%LOGO_NASAPAY%" >nul
)

:: ---------------- Criar atalhos (Desktop + Menu Iniciar) ----------------
echo.
echo Criando atalhos...

:: Atalho na Area de Trabalho (todos os usuarios)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$W=(New-Object -ComObject WScript.Shell);" ^
  "$D=[Environment]::GetFolderPath('CommonDesktopDirectory');" ^
  "$S=$W.CreateShortcut(($D+'\Nasapay.lnk'));" ^
  "$S.TargetPath='%TARGET%\%EXE%';" ^
  "$S.WorkingDirectory='%TARGET%';" ^
  "$S.IconLocation='%TARGET%\%EXE%,0';" ^
  "$S.Save()"

:: Atalho no Menu Iniciar (usuario atual)
if not exist "%STARTMENU%" mkdir "%STARTMENU%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$W=(New-Object -ComObject WScript.Shell);" ^
  "$S=$W.CreateShortcut('%STARTMENU%\Nasapay.lnk');" ^
  "$S.TargetPath='%TARGET%\%EXE%';" ^
  "$S.WorkingDirectory='%TARGET%';" ^
  "$S.IconLocation='%TARGET%\%EXE%,0';" ^
  "$S.Save()"

:: ---------------- Fixar na Barra de Tarefas (best-effort) ----------------
echo Fixando na barra de tarefas (pode levar alguns segundos)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$lnk = '%STARTMENU%\Nasapay.lnk';" ^
  "if (-not (Test-Path $lnk)) {" ^
  "  $W=New-Object -ComObject WScript.Shell; $S=$W.CreateShortcut($lnk);" ^
  "  $S.TargetPath='%TARGET%\%EXE%'; $S.WorkingDirectory='%TARGET%'; $S.IconLocation='%TARGET%\%EXE%,0'; $S.Save()" ^
  "};" ^
  "$Shell = New-Object -ComObject Shell.Application;" ^
  "$Folder = $Shell.Namespace((Split-Path $lnk));" ^
  "$Item = $Folder.ParseName((Split-Path $lnk -Leaf));" ^
  "$verbs = @('taskbarpin','Pin to taskbar','Fixar na barra de tarefas');" ^
  "foreach($v in $verbs){ try { $Item.InvokeVerb($v) } catch {} }"

echo.
echo ===============================================
echo  Instalacao concluida em "%TARGET%"
echo  Pastas criadas:
echo    - %TARGET%\Arquivos
echo    - %TARGET%\Remessa
echo    - %TARGET%\Retorno
echo    - %TARGET%\Boletos
echo ===============================================
echo Abrindo o Nasapay...

start "" "%TARGET%\%EXE%"
exit /b 0
