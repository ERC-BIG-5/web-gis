#!/usr/bin/env bash
# Build the frontend into web/dist. Uses system npm if present, otherwise a
# Node runtime fetched via uv (no system-wide Node install needed).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/web"

if command -v npm >/dev/null 2>&1; then
    NPM=(npm)
else
    NPM=(uvx --from nodejs-wheel npm)
fi

[ -d node_modules ] || "${NPM[@]}" ci
"${NPM[@]}" run build
