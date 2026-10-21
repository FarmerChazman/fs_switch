#!/usr/bin/env bash
# Creates the Frappe v16 bench at $FS_SWITCH_BENCH. Run once.
set -e
source "$(dirname "$0")/env.sh"

[ -d "$FS_SWITCH_VENV" ] || uv venv -q -p "$FS_SWITCH_PYTHON" "$FS_SWITCH_VENV"
uv pip install -q --python "$FS_SWITCH_VENV/bin/python" frappe-bench
export PATH="$FS_SWITCH_VENV/bin:$PATH"

cd "$FS_SWITCH_ROOT"
if [ ! -d "$FS_SWITCH_BENCH" ]; then
  bench init --frappe-branch version-16 --python "$FS_SWITCH_VENV/bin/python" "$FS_SWITCH_BENCH"
fi
echo BENCH_INIT_DONE
