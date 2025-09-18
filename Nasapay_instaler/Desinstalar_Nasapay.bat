@echo off
setlocal

:: ============================================================
::  Desinstalar_Nasapay.bat — remove app, pastas e atalhos
:: ============================================================

:: ----------- Elevar para Administrador (UAC) -----------
>nul 2>&1 net session
if %errorlevel% neq 0 (
  echo Solicitando permissao de administrador...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

:: ----------- Variaveis -----------
set "TARGET=C:\nasapay"
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Nasapay"
set "DESKTOP_COMMON=%Public%\Desktop"

echo.
echo ===============================================
echo  Desinstalando Nasapay...
echo ===============================================

:: ----------- Fechar app se estiver aberto -----------
echo Encerrando processo Nasapay (se existir)...
taskkill /im Nasapay.exe /f >nul 2>&1

:: ----------- Desafixar da Barra de Tarefas (best-effort) -----------
echo Desafixando da barra de tarefas...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$lnk = '%STARTMENU%\Nasapay.lnk';" ^
  "if (Test-Path $lnk) {" ^
  "  $Shell = New-Object -ComObject Shell.Application;" ^
  "  $Folder = $Shell.Namespace((Split-Path $lnk));" ^
  "  $Item = $Folder.ParseName((Split-Path $lnk -Leaf));" ^
  "  $verbs = @('taskbarunpin','Unpin from taskbar','Desafixar da barra de tarefas');" ^
  "  foreach($v in $verbs){ try { $Item.InvokeVerb($v) } catch {} }" ^
  "}"

:: ----------- Remover atalhos -----------
echo Removendo atalhos...
del /q "%DESKTOP_COMMON%\Nasapay.lnk" 2>nul
if exist "%STARTMENU%\Nasapay.lnk" del /q "%STARTMENU%\Nasapay.lnk" 2>nul
if exist "%STARTMENU%" rmdir /s /q "%STARTMENU%" 2>nul

:: ----------- Remover pasta principal -----------
if exist "%TARGET%" (
  echo Removendo pasta %TARGET% ...
  rmdir /s /q "%TARGET%"
) else (
  echo Pasta %TARGET% nao encontrada.
)

echo.
echo ===============================================
echo  Desinstalacao concluida.
echo ===============================================
pause
exit /b 0
