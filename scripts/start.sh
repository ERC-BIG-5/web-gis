#!/usr/bin/env bash
# Run the server in the foreground. Port/host come from server/.env
# (copy server/.env.template) or from the environment, e.g. PORT=9000 ./scripts/start.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Rebuild frontend only if npm has been initialized in web/.
# Fresh clones use the prebuilt web/dist/ shipped in the repo.
if [ -d "$ROOT/web/node_modules" ]; then
    "$ROOT/scripts/build.sh"
fi

cd "$ROOT/server"
exec uv run python main.py
