#!/usr/bin/env bash
# Shared environment for the local/bench scripts. Docker sets these directly.
set -a
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$ROOT/.env" ] && . "$ROOT/.env"
set +a

export FS_SWITCH_ROOT="${FS_SWITCH_ROOT:-$ROOT}"
export FS_SWITCH_BENCH="${FS_SWITCH_BENCH:-$ROOT/frappe-bench}"
export FS_SWITCH_VENV="${FS_SWITCH_VENV:-$ROOT/venv}"
export FS_SWITCH_PYTHON="${FS_SWITCH_PYTHON:-python3.14}"
export FS_SWITCH_SITE="${FS_SWITCH_SITE:-fs-switch.localhost}"
export PATH="$FS_SWITCH_VENV/bin:$HOME/.local/bin:$PATH"
