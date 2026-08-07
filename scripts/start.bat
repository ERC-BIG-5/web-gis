@echo off
setlocal
set SCRIPT_DIR=%~dp0
set ROOT=%SCRIPT_DIR%..

REM Rebuild frontend only if npm has been initialized in web\.
REM Fresh clones use the prebuilt web\dist\ shipped in the repo.
if exist "%ROOT%\web\node_modules" (
    pushd "%ROOT%\web"
    call npm run build
    popd
)

cd /d "%ROOT%\server"
uv run python main.py
endlocal
