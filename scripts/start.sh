#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Rebuild frontend only if npm has been initialized in web/.
# Fresh clones use the prebuilt web/dist/ shipped in the repo.
if [ -d "$ROOT/web/node_modules" ]; then
    (cd "$ROOT/web" && npm run build)
fi

cd "$ROOT/server"
exec uv run python main.py
