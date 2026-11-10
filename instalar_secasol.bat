@echo off
rem ===========================================================================
rem  Instalador de Secasol - Windows 10 / 11
rem ===========================================================================
rem  Crea un entorno virtual de Python dentro de la carpeta del proyecto (.venv)
rem  e instala las MISMAS versiones de librerias que corre la version en
rem  produccion (requirements.txt). No toca nada fuera de esta carpeta.
rem
rem  Uso: doble clic sobre este archivo, o desde una consola en la carpeta:
rem      instalar_secasol.bat             uso normal
rem      instalar_secasol.bat --iniciar   instala y abre la aplicacion
rem      instalar_secasol.bat --dev       + pytest, black y ruff (desarrollo)
rem      instalar_secasol.bat --limpio    borra .venv y lo crea de nuevo
rem
rem  Despues, para abrir la aplicacion: doble clic en iniciar_secasol.bat
rem
rem  Requisitos: Python 3.11 o superior (se recomienda 3.13, la de produccion),
rem  instalado desde https://www.python.org/downloads/ con la opcion
rem  "Add python.exe to PATH" marcada, y conexion a internet.
rem ===========================================================================
setlocal
cd /d "%~dp0"

set "DEV=0"
set "INICIAR=0"
set "LIMPIO=0"
:leer_args
if "%~1"=="" goto args_listos
if /i "%~1"=="--dev" (set "DEV=1" & shift & goto leer_args)
if /i "%~1"=="--iniciar" (set "INICIAR=1" & shift & goto leer_args)
if /i "%~1"=="--limpio" (set "LIMPIO=1" & shift & goto leer_args)
echo [ERROR] Opcion desconocida: %~1
goto fallo
:args_listos

if not exist "requirements.txt" goto sin_proyecto
if not exist "Secasol.py" goto sin_proyecto

echo.
echo ==============================================
echo   Secasol - instalacion local
echo ==============================================

rem ---------------------------------------------------------------------------
rem 1. Python: primero el lanzador "py" (3.13 = produccion), despues "python".
rem ---------------------------------------------------------------------------
set "PY="
for %%V in (3.13 3.12 3.14 3.11) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
    )
)
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY goto sin_python

echo [OK] Python encontrado:
%PY% --version
%PY% -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [!!] Produccion usa Python 3.13. Con otra version la app funciona, pero algun
    echo      resultado numerico puede diferir en los ultimos decimales.
)

rem ---------------------------------------------------------------------------
rem 2. Entorno virtual
rem ---------------------------------------------------------------------------
if "%LIMPIO%"=="1" if exist ".venv" (
    echo [..] Borrando el entorno anterior .venv ...
    rmdir /s /q ".venv"
)
if exist ".venv" (
    ".venv\Scripts\python.exe" -m pip --version >nul 2>&1
    if errorlevel 1 (
        echo [!!] Hay un .venv que no sirve ^(sin Python o sin pip^). Se crea uno nuevo.
        rmdir /s /q ".venv"
    )
)
if not exist ".venv" (
    echo [..] Creando el entorno virtual en .venv ...
    %PY% -m venv ".venv"
    if errorlevel 1 goto sin_venv
    echo [OK] Entorno virtual creado.
) else (
    echo [OK] Se reutiliza el entorno existente .venv  ^(usar --limpio para rehacerlo^)
)
set "VPY=.venv\Scripts\python.exe"

rem ---------------------------------------------------------------------------
rem 3. Librerias
rem ---------------------------------------------------------------------------
set "REQ=requirements.txt"
if "%DEV%"=="1" set "REQ=requirements-dev.txt"

echo [..] Actualizando pip...
"%VPY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
if errorlevel 1 goto fallo_pip
echo [..] Instalando librerias de %REQ% (la primera vez tarda unos minutos)...
"%VPY%" -m pip install -r "%REQ%" --disable-pip-version-check
if errorlevel 1 goto fallo_pip
echo [OK] Librerias instaladas.

rem ---------------------------------------------------------------------------
rem 4. Verificacion
rem ---------------------------------------------------------------------------
echo [..] Verificando la instalacion...
"%VPY%" -c "import streamlit, numpy, scipy, pandas, pvlib, plotly, kaleido, reportlab, yaml, pyarrow, openpyxl, xlrd, calculos.balance_global, ui.p7_resultados; from core.version import __version__ as v; print('[OK] Secasol ' + v + ' listo.')"
if errorlevel 1 (
    echo [ERROR] La verificacion fallo ^(ver el error de arriba^).
    goto fallo
)

if "%DEV%"=="1" (
    echo.
    echo Herramientas de desarrollo instaladas. Suite completa ^(~10 min^):
    echo     .venv\Scripts\python.exe -m pytest
)

echo.
echo Para abrir la aplicacion: doble clic en iniciar_secasol.bat
echo Se abre en el navegador ^(http://localhost:8501^). Para cerrarla, cerrar la ventana negra.
echo.
if "%INICIAR%"=="1" (
    endlocal
    call "%~dp0iniciar_secasol.bat"
    exit /b 0
)
pause
exit /b 0

rem ---------------------------------------------------------------------------
:sin_proyecto
echo [ERROR] No encuentro requirements.txt / Secasol.py junto a este archivo.
echo         Ejecutar el instalador desde la carpeta del repositorio de Secasol.
goto fallo

:sin_python
echo [ERROR] No encontre Python 3.11 o superior.
echo         1. Descargar Python 3.13 desde https://www.python.org/downloads/
echo         2. En el instalador, marcar "Add python.exe to PATH".
echo         3. Cerrar esta ventana y volver a ejecutar instalar_secasol.bat
goto fallo

:sin_venv
echo [ERROR] No se pudo crear el entorno virtual.
echo         Reinstalar Python desde python.org con las opciones por defecto.
goto fallo

:fallo_pip
echo [ERROR] Fallo la instalacion de librerias. Revisar la conexion a internet
echo         y volver a ejecutar con:  instalar_secasol.bat --limpio
goto fallo

:fallo
echo.
pause
exit /b 1
