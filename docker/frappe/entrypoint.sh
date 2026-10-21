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

if [ ! -d "sites/$FS_SWITCH_SITE" ]; then
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
