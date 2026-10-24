#!/usr/bin/env bash
# Starts the Frappe container: waits for MariaDB/Redis, creates the site on first
# boot, applies container settings, starts the ESL listener and runs the bench.
set -e
source "$FS_SWITCH_ROOT/env.sh"
cd "$FS_SWITCH_BENCH"

echo "waiting for MariaDB..."
for _ in $(seq 1 60); do
  mysqladmin ping -h "${FRAPPE_DB_HOST:-db}" -u root -p"$FS_SWITCH_DB_ROOT_PASSWORD" --silent 2>/dev/null && break
  sleep 2
done
echo "waiting for Redis..."
for _ in $(seq 1 30); do
  redis-cli -u "${FRAPPE_REDIS_CACHE:-redis://redis-cache:6379}" ping >/dev/null 2>&1 && break
  sleep 2
done

bench set-config -g db_host "${FRAPPE_DB_HOST:-db}"
bench set-config -g redis_cache "${FRAPPE_REDIS_CACHE:-redis://redis-cache:6379}"
bench set-config -g redis_queue "${FRAPPE_REDIS_QUEUE:-redis://redis-queue:6379}"
bench set-config -g default_site "$FS_SWITCH_SITE"
bench set-config -g webserver_port 8000
bench set-config -g socketio_port 9000

# The site lives in a persistent volume; the app source lives in the image.
# On an upgrade, replace the bench copy with the image's current source so the
# new Python code and built console assets are used with the existing site.
if [ -d "sites/$FS_SWITCH_SITE" ]; then
  echo "syncing FS Switch app source"
  rm -rf apps/fs_switch
  cp -r "$FS_SWITCH_ROOT/apps/fs_switch" apps/
  rm -rf apps/fs_switch/frontend/node_modules

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
  bench --site "$FS_SWITCH_SITE" migrate
else
  echo "first start: creating site, installing FS Switch and building the console"
  bash "$FS_SWITCH_ROOT/setup_apps.sh"
fi

# Values shared with the FreeSWITCH container. Safe to run on every start.
bench --site "$FS_SWITCH_SITE" execute fs_switch.setup.configure_from_env

# bench start does not run app background processes, so start the listener here.
mkdir -p "$FS_SWITCH_ROOT/logs"
nohup bench --site "$FS_SWITCH_SITE" execute fs_switch.esl_listener.run \
  >> "$FS_SWITCH_ROOT/logs/esl-listener.log" 2>&1 &

echo "starting bench on :8000"
exec bench start
