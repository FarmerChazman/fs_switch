#!/usr/bin/env bash
# Creates the site, installs the local FS Switch app and builds the console.
set -e
source "$(dirname "$0")/env.sh"

cd "$FS_SWITCH_BENCH"
if [ ! -d "sites/$FS_SWITCH_SITE" ]; then
  bench new-site "$FS_SWITCH_SITE" \
    --mariadb-root-password "${FS_SWITCH_DB_ROOT_PASSWORD:?set FS_SWITCH_DB_ROOT_PASSWORD}" \
    --admin-password "${FS_SWITCH_ADMIN_PASSWORD:?set FS_SWITCH_ADMIN_PASSWORD}" \
    --db-name fs_switch
fi

if [ ! -d apps/fs_switch ]; then
  cp -r "$FS_SWITCH_ROOT/apps/fs_switch" apps/
fi

# This app is copied rather than cloned. Do what get-app would have done:
# register it in sites/apps.txt and install it editable before install-app
# imports its hooks.
env/bin/python - <<'PY'
from pathlib import Path
p = Path("sites/apps.txt")
apps = [a.strip() for a in p.read_text().splitlines() if a.strip()]
if "fs_switch" not in apps:
    apps.append("fs_switch")
    p.write_text("\n".join(apps) + "\n")
PY
if ! env/bin/python -c "import fs_switch" >/dev/null 2>&1; then
  uv pip install --python env/bin/python -e apps/fs_switch
fi

bench --site "$FS_SWITCH_SITE" install-app fs_switch
bench --site "$FS_SWITCH_SITE" migrate

# The website/login bundles are built after a new site in a fresh bench.
bench build --app frappe

cd apps/fs_switch/frontend
npm install --no-audit --no-fund
npm run build

echo APP_INSTALL_DONE
