#!/usr/bin/env sh
# Wrapper fino (Linux/macOS): localiza Python 3 e chama o instalador real.
# Toda a lógica vive em install-squad-ai.py (DRY). Repassa os argumentos.
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "Erro: Python 3 não encontrado no PATH." >&2
  exit 1
fi
exec "$PY" "$DIR/install-squad-ai.py" "$@"
