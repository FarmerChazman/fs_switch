#!/usr/bin/env bash
# Write the FreeSWITCH config from the environment, then run FreeSWITCH in the
# foreground. No secrets are baked into the image.
set -e

SRC="${FS_SWITCH_TEST_SRC:-/opt/fs-switch/freeswitch}"
ETC="${FS_SWITCH_TEST_ETC:-/etc/freeswitch}"
VAR="${FS_SWITCH_TEST_VAR:-/var/lib/freeswitch}"
: "${FRAPPE_URL:=http://frappe:8000}"
: "${FS_SWITCH_XML_CURL_SECRET:?set FS_SWITCH_XML_CURL_SECRET in .env}"
: "${FS_SWITCH_ESL_PASSWORD:?set FS_SWITCH_ESL_PASSWORD in .env}"
: "${FS_SWITCH_PUBLIC_IP:=127.0.0.1}"
: "${FS_SWITCH_SIP_DOMAIN:=localhost}"
: "${RTP_START:=16384}"
: "${RTP_END:=16484}"

# Enable the modules this project needs (the stock samples ship them commented out).
sed -i \
  -e 's|<!-- *<load module="mod_xml_curl"/> *-->|<load module="mod_xml_curl"/>|' \
  -e 's|<!-- *<load module="mod_callcenter"/> *-->|<load module="mod_callcenter"/>|' \
  "$ETC/autoload_configs/modules.conf.xml"
# These modules are disabled in the build because their optional dependencies
# are not installed. Comment the stock loads to avoid CRIT noise.
sed -i \
  -e 's|^\(\s*\)<load module="mod_av"/>|\1<!-- mod_av not available in this image -->|' \
  -e 's|^\(\s*\)<load module="mod_verto"/>|\1<!-- mod_verto not available in this image -->|' \
  -e 's|^\(\s*\)<load module="mod_signalwire"/>|\1<!-- mod_signalwire not available in this image -->|' \
  -e 's|^\(\s*\)<load module="mod_spandsp"/>|\1<!-- mod_spandsp not available in this image -->|' \
  "$ETC/autoload_configs/modules.conf.xml"

# Directory, dialplan and callcenter.conf come from Frappe (mod_xml_curl).
install -m 640 "$SRC/conf/autoload_configs/xml_curl.conf.xml" "$ETC/autoload_configs/xml_curl.conf.xml"
sed -i "s|https://freeswitch.example.com/api/method/fs_switch.api.xml_curl?secret=SECRET|${FRAPPE_URL}/api/method/fs_switch.api.xml_curl?secret=${FS_SWITCH_XML_CURL_SECRET}|g" \
  "$ETC/autoload_configs/xml_curl.conf.xml"
install -m 640 "$SRC/conf/sip_profiles/webrtc.xml" "$ETC/sip_profiles/webrtc.xml"
sed -i "s|<param name=\"context\" value=\"default\"/>|<param name=\"context\" value=\"${FS_SWITCH_DEFAULT_CONTEXT:-default}\"/>|" \
  "$ETC/sip_profiles/webrtc.xml"

# A carrier gateway is optional. Write one only when the operator supplied a proxy.
if [ -n "${FS_SWITCH_TRUNK_PROXY:-}" ]; then
  cat > "$ETC/sip_profiles/external/carrier.xml" <<EOF
<include>
  <gateway name="carrier">
    <param name="proxy" value="${FS_SWITCH_TRUNK_PROXY}"/>
    <param name="realm" value="${FS_SWITCH_TRUNK_REALM:-$FS_SWITCH_TRUNK_PROXY}"/>
    <param name="username" value="${FS_SWITCH_TRUNK_USERNAME:-}"/>
    <param name="password" value="${FS_SWITCH_TRUNK_PASSWORD:-}"/>
    <param name="register" value="true"/>
    <param name="caller-id-in-from" value="true"/>
    <param name="extension-in-contact" value="true"/>
    <param name="from-domain" value="${FS_SWITCH_TRUNK_REALM:-$FS_SWITCH_TRUNK_PROXY}"/>
  </gateway>
</include>
EOF
  chown freeswitch:freeswitch "$ETC/sip_profiles/external/carrier.xml"
  chmod 640 "$ETC/sip_profiles/external/carrier.xml"
fi

# The internal profile must not bind the WebSocket ports (the webrtc profile does).
sed -i -e 's|^\(\s*\)<param name="ws-binding"  *value=":5066"/>|\1<!-- ws-binding moved to webrtc profile -->|' \
       -e 's|^\(\s*\)<param name="wss-binding" *value=":7443"/>|\1<!-- wss-binding moved to webrtc profile -->|' \
       "$ETC/sip_profiles/internal.xml"

# Event socket: listen on all interfaces inside the Docker network (not published).
# mod_event_socket defaults to the loopback ACL, which rejects the separate
# Frappe container; lan covers the private Docker network without opening it to
# the public internet.
sed -i -e 's|<param name="listen-ip" value="[^"]*"/>|<param name="listen-ip" value="0.0.0.0"/>|' \
       -e "s|<param name=\"password\" value=\"[^\"]*\"/>|<param name=\"password\" value=\"${FS_SWITCH_ESL_PASSWORD}\"/>|" \
       "$ETC/autoload_configs/event_socket.conf.xml"
sed -i '/<param name="listen-port" value="8021"\/>/a\    <param name="apply-inbound-acl" value="lan"/>' \
       "$ETC/autoload_configs/event_socket.conf.xml"

# Domain and media addresses.
sed -i -e "s|\(data=\"domain=\)[^\"]*\"|\1${FS_SWITCH_SIP_DOMAIN}\"|" "$ETC/vars.xml" || true
sed -i -e "s|\(external_rtp_ip=\)[^\"]*\"|\1${FS_SWITCH_PUBLIC_IP}\"|" \
       -e "s|\(external_sip_ip=\)[^\"]*\"|\1${FS_SWITCH_PUBLIC_IP}\"|" "$ETC/vars.xml"
sed -i -e "s|<!-- *<param name=\"rtp-start-port\" value=\"[0-9]*\"/> *-->|<param name=\"rtp-start-port\" value=\"${RTP_START}\"/>|" \
       -e "s|<!-- *<param name=\"rtp-end-port\" value=\"[0-9]*\"/> *-->|<param name=\"rtp-end-port\" value=\"${RTP_END}\"/>|" \
       -e "s|\(name=\"rtp-start-port\" value=\"\)[0-9]*\"|\1${RTP_START}\"|" \
       -e "s|\(name=\"rtp-end-port\" value=\"\)[0-9]*\"|\1${RTP_END}\"|" \
       "$ETC/autoload_configs/switch.conf.xml"

mkdir -p "$VAR" "$ETC/tls"
# WebRTC TLS: use a real certificate in the tls volume; otherwise generate a
# self-signed one for local development (browsers will not accept wss:// with it).
if [ ! -f "$ETC/tls/wss.pem" ]; then
  echo "no TLS certificate found: creating a self-signed one for local testing (use ws://localhost:5066)"
  openssl req -x509 -newkey rsa:2048 -nodes -keyout /tmp/key.pem -out /tmp/cert.pem -days 365 -subj "/CN=localhost" 2>/dev/null
  cat /tmp/cert.pem /tmp/key.pem > "$ETC/tls/wss.pem"
  rm -f /tmp/key.pem /tmp/cert.pem
fi

[ -n "${FS_SWITCH_TEST_DRYRUN:-}" ] && {
  echo "dry run: config written, FreeSWITCH not started"
  exit 0
}

echo "starting FreeSWITCH (directory from ${FRAPPE_URL}, media ${FS_SWITCH_PUBLIC_IP}, RTP ${RTP_START}-${RTP_END})"
exec /usr/bin/freeswitch -nonat -nf -c
