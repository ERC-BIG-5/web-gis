#!/usr/bin/env bash
# Run the server in the foreground. Port/host come from server/.env
# (copy server/.env.template) or from the environment, e.g. PORT=9000 ./scripts/start.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Build the frontend when web/dist is missing (fresh clone; web/dist is not
# tracked) or when npm has been set up in web/ (frontend development).
if [ ! -f "$ROOT/web/dist/index.html" ] || [ -d "$ROOT/web/node_modules" ]; then
    "$ROOT/scripts/build.sh"
fi

cd "$ROOT/server"
exec uv run python main.py
