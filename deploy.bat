@echo off
:: ══════════════════════════════════════════════════════════════
::  BESS Dashboard — Deploy a GitHub Pages
::  Doble-click para publicar la ultima version del dashboard
:: ══════════════════════════════════════════════════════════════
chcp 65001 >nul
setlocal

:: ── Ruta de Python ───────────────────────────────────────────
set PYTHON=C:\Users\wbanos\AppData\Local\Python\bin\python.exe

:: ── Fecha para el commit ─────────────────────────────────────
for /f "tokens=1-3 delims=/" %%a in ("%date%") do (
    set DIA=%%a
    set MES=%%b
    set ANO=%%c
)
set FECHA_COMMIT=%DIA%/%MES%/%ANO%

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   BESS Dashboard · Deploy a GitHub Pages     ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: ── 1. Regenerar dashboard ───────────────────────────────────
echo [1/4] Regenerando dashboard...
"%PYTHON%" build_dashboard.py
if errorlevel 1 (
    echo.
    echo  ERROR: Fallo build_dashboard.py
    pause
    exit /b 1
)
echo        OK

:: ── 2. Copiar a docs/ ────────────────────────────────────────
echo [2/4] Copiando a docs/index.html...
copy /Y "outputs\dashboard_bess.html" "docs\index.html" >nul
if errorlevel 1 (
    echo  ERROR: No se pudo copiar el archivo
    pause
    exit /b 1
)
echo        OK

:: ── 3. Git add + commit ──────────────────────────────────────
echo [3/4] Haciendo commit...
git add docs/index.html docs/.nojekyll
git commit -m "Dashboard actualizado %FECHA_COMMIT%"
if errorlevel 1 (
    echo        (sin cambios que commitear)
)

:: ── 4. Push ──────────────────────────────────────────────────
echo [4/4] Publicando en GitHub...
git push origin main
if errorlevel 1 (
    echo.
    echo  ERROR: Fallo el push. Verifica tu conexion y credenciales.
    pause
    exit /b 1
)

echo.
echo  ✅ Dashboard publicado exitosamente!
echo     URL: https://wilfjosue.github.io/bess-dashboard/
echo.
pause
