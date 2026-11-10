@echo off
rem ===========================================================================
rem  Abre Secasol en el navegador - Windows 10 / 11
rem ===========================================================================
rem  Uso: doble clic sobre este archivo.
rem  Requiere haber ejecutado antes instalar_secasol.bat
rem  Para cerrar la aplicacion: cerrar esta ventana (o Ctrl+C).
rem  Argumentos extra se pasan a Streamlit (ej.: --server.port 8600).
rem ===========================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto sin_instalar
".venv\Scripts\python.exe" -c "import streamlit" >nul 2>&1
if errorlevel 1 goto sin_instalar

echo Abriendo Secasol en el navegador (la direccion aparece abajo, normalmente http://localhost:8501^)...
echo Para cerrarla: cerrar esta ventana.
echo.

rem showEmailPrompt=false: sin esto, la primera vez Streamlit se queda esperando
rem un email en la consola y la aplicacion nunca arranca.
".venv\Scripts\python.exe" -m streamlit run Secasol.py --server.showEmailPrompt false --browser.gatherUsageStats false %*
exit /b %errorlevel%

:sin_instalar
echo [ERROR] Secasol no esta instalado en esta carpeta.
echo         Ejecutar primero instalar_secasol.bat
echo.
pause
exit /b 1
