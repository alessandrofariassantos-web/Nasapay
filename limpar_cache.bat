@echo off
echo Limpando cache Python do Nasapay...
cd /d C:\nasapay

echo.
echo Removendo diretorios __pycache__...
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" (
        echo Removendo: %%d
        rmdir /s /q "%%d"
    )
)

echo.
echo Removendo arquivos .pyc...
for /r . %%f in (*.pyc) do (
    if exist "%%f" (
        echo Removendo: %%f
        del /q "%%f"
    )
)

echo.
echo Removendo arquivos .pyo...
for /r . %%f in (*.pyo) do (
    if exist "%%f" (
        echo Removendo: %%f
        del /q "%%f"
    )
)

echo.
echo Verificando se ainda existe cache...
dir /s __pycache__ 2>nul && echo AVISO: Ainda existem diretorios __pycache__ || echo OK: Nenhum __pycache__ encontrado
dir /s *.pyc 2>nul && echo AVISO: Ainda existem arquivos .pyc || echo OK: Nenhum .pyc encontrado

echo.
echo Limpeza concluida!
pause
