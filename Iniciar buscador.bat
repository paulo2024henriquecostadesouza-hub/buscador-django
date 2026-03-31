@echo off
title Buscador de Servicos - Porta 8507

:: Sai do contexto UNC (CMD padroniza para Windows, isso e normal)
cd /d %USERPROFILE%

:: pushd no share sem acentos - cria mapeamento temporario de drive
pushd \\10.1.1.140\Cco_Centro_de_Controle_Operacional
if errorlevel 1 (
    echo [ERRO] Nao foi possivel acessar 10.1.1.140
    pause
    exit /b 1
)

:: Navega ate Paulo sem acentos
cd CCO\Paulo

:: Encontra a pasta acentuada em runtime sem precisar escreve-la no bat
for /f "delims=" %%D in ('dir /b /ad .') do (
    if exist "%%D\Buscador-Django\manage.py" (
        cd "%%D\Buscador-Django"
        goto :iniciar
    )
)

echo [ERRO] Pasta Buscador-Django nao encontrada
popd
pause
exit /b 1

:iniciar
echo.
echo  Buscador de Servicos - ON
echo  Acesse: http://10.1.1.27:8507
echo.
python manage.py runserver 0.0.0.0:8507 --noreload

popd
pause
