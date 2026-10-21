#!/usr/bin/env bash
# Install the FS Switch configs after build-freeswitch.sh. Run as root from the
# freeswitch/ directory: sudo bash install/install-config.sh
set -euo pipefail
cd "$(dirname "$0")/.."

[ -d /etc/freeswitch ] || {
  echo "FreeSWITCH is not installed. Run install/build-freeswitch.sh first."
  exit 1
}

echo "== 1. Enable the modules FS Switch needs"
M=/etc/freeswitch/autoload_configs/modules.conf.xml
sed -i \
  -e 's|<!-- *<load module="mod_xml_curl"/> *-->|<load module="mod_xml_curl"/>|' \
  -e 's|<!-- *<load module="mod_callcenter"/> *-->|<load module="mod_callcenter"/>|' \
  "$M"
grep -q 'load module="mod_xml_curl"' "$M"
grep -q 'load module="mod_callcenter"' "$M"

echo "== 2. Event socket listens on localhost only"
sed -i 's|<param name="listen-ip" value="[^"]*"/>|<param name="listen-ip" value="127.0.0.1"/>|' \
  /etc/freeswitch/autoload_configs/event_socket.conf.xml

echo "== 3. Copy configs"
install -m 640 -o freeswitch -g freeswitch conf/autoload_configs/xml_curl.conf.xml /etc/freeswitch/autoload_configs/
install -m 640 -o freeswitch -g freeswitch conf/sip_profiles/webrtc.xml /etc/freeswitch/sip_profiles/
# Only install the carrier template if the operator has filled it in.
if ! grep -q 'TRUNK_' conf/sip_profiles/external/example_trunk.xml; then
  install -m 640 -o freeswitch -g freeswitch conf/sip_profiles/external/example_trunk.xml /etc/freeswitch/sip_profiles/external/
fi

# The stock internal profile also binds the WebSocket ports, which clash with
# the webrtc profile. Only the webrtc profile may bind 5066/7443.
sed -i -e 's|^\(\s*\)<param name="ws-binding"  *value=":5066"/>|\1<!-- ws-binding moved to webrtc profile -->|' \
       -e 's|^\(\s*\)<param name="wss-binding" *value=":7443"/>|\1<!-- wss-binding moved to webrtc profile -->|' \
       /etc/freeswitch/sip_profiles/internal.xml

echo "== 4. Refuse to continue with placeholder values"
if grep -q 'SECRET' /etc/freeswitch/autoload_configs/xml_curl.conf.xml; then
  echo "Edit /etc/freeswitch/autoload_configs/xml_curl.conf.xml and replace SECRET, then run this again."
  exit 2
fi

echo "== 5. Start and check"
echo "Set the ESL password in /etc/freeswitch/autoload_configs/event_socket.conf.xml"
echo "and use the same value in FS Switch Settings."
systemctl enable --now freeswitch
sleep 5
fs_cli -x "reloadxml" || true
fs_cli -x "show modules" | grep -E "mod_xml_curl|mod_callcenter|mod_sofia" || echo "WARNING: expected modules not listed"
fs_cli -x "sofia status" | head -20
echo CONFIG_DONE
