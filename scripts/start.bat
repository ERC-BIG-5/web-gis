@echo off
setlocal
set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..

REM Use system npm if present, otherwise a Node runtime fetched via uv.
set "NPM=npm"
where npm >nul 2>&1 || set "NPM=uvx --from nodejs-wheel npm"

REM Build the frontend when web\dist is missing (fresh clone; web\dist is not
REM tracked) or when npm has been set up in web\ (frontend development).
set NEED_BUILD=
if exist "%ROOT%\web\node_modules" set NEED_BUILD=1
if not exist "%ROOT%\web\dist\index.html" set NEED_BUILD=1
if defined NEED_BUILD (
    pushd "%ROOT%\web"
    if not exist node_modules call %NPM% ci
    call %NPM% run build
    popd
)

cd /d "%ROOT%\server"
uv run webgis-server
endlocal
