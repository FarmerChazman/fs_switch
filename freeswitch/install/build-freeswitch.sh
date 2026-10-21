#!/bin/bash
# Builds FreeSWITCH from source on Ubuntu 24.04 and installs it to /usr with config in /etc/freeswitch.
# Run as root:  sudo bash build-freeswitch.sh
# Takes roughly 30-60 minutes on a 2-core server. Re-running is safe.
set -euo pipefail

FS_TAG=${FS_TAG:-v1.10.12}          # FreeSWITCH release to build
SOFIA_TAG=v1.13.18                  # minimum sofia-sip-ua 1.13.18 (Ubuntu's 1.12.x is too old)
SPANDSP_TAG=v3.1.1                  # minimum spandsp 3.1.1 (Ubuntu's 0.0.6 is too old)
SRC=${SRC:-/usr/local/src}
JOBS=${JOBS:-$(nproc)}

echo "== 1. Build dependencies"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq || echo "apt update had warnings; continuing"
apt-get install -y -qq build-essential autoconf automake libtool libtool-bin pkg-config git \
  yasm nasm \
  libssl-dev libcurl4-openssl-dev libpcre2-dev libsqlite3-dev libspeex-dev libspeexdsp-dev \
  libpcre3-dev libldns-dev libedit-dev libopus-dev libsndfile1-dev libjpeg-dev uuid-dev zlib1g-dev \
  libncurses-dev libxml2-dev libpq-dev libmemcached-dev libtiff-dev liblua5.4-dev \
  libgdbm-dev libtpl-dev libsrtp2-dev ffmpeg

mkdir -p "$SRC"; cd "$SRC"

echo "== 2. sofia-sip $SOFIA_TAG (if the system one is older)"
if ! pkg-config --atleast-version=1.13.18 sofia-sip-ua 2>/dev/null; then
  [ -d sofia-sip ] || git clone -q --depth 1 --branch "$SOFIA_TAG" https://github.com/freeswitch/sofia-sip
  (cd sofia-sip && ./bootstrap.sh >/dev/null && ./configure --prefix=/usr/local >/dev/null && make -j"$JOBS" >/dev/null && make install >/dev/null)
fi

echo "== 3. spandsp $SPANDSP_TAG (if the system one is older)"
if ! pkg-config --atleast-version=3.1.1 spandsp 2>/dev/null; then
  [ -d spandsp ] || git clone -q --depth 1 --branch "$SPANDSP_TAG" https://github.com/freeswitch/spandsp
  (cd spandsp && ./bootstrap.sh >/dev/null && ./configure --prefix=/usr/local >/dev/null && make -j"$JOBS" >/dev/null && make install >/dev/null)
fi
ldconfig
export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH:-}

echo "== 4. FreeSWITCH $FS_TAG"
if [ ! -d freeswitch ]; then
  git clone -q --depth 1 --branch "$FS_TAG" https://github.com/signalwire/freeswitch
fi
cd freeswitch
./bootstrap.sh >/dev/null

# Modules disabled by default that this project needs
cp build/modules.conf.in modules.conf
sed -i \
  -e 's|^#applications/mod_callcenter|applications/mod_callcenter|' \
  -e 's|^#xml_int/mod_xml_curl|xml_int/mod_xml_curl|' \
  -e 's|^endpoints/mod_verto|#endpoints/mod_verto|' \
  -e 's|^applications/mod_signalwire|#applications/mod_signalwire|' \
  -e 's|^languages/mod_python3|#languages/mod_python3|' \
  -e 's|^applications/mod_av|#applications/mod_av|' \
  -e 's|^applications/mod_spandsp|#applications/mod_spandsp|' \
  modules.conf
grep -q "^applications/mod_callcenter" modules.conf && grep -q "^xml_int/mod_xml_curl" modules.conf

./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var --with-lua=yes --without-python --without-python3 > /tmp/fs-configure.log 2>&1 \
  || { echo "configure failed, last 80 lines:"; tail -80 /tmp/fs-configure.log; exit 1; }
make -j"$JOBS" > /tmp/fs-make.log 2>&1 \
  || { echo "make failed, last 120 lines:"; tail -120 /tmp/fs-make.log; exit 1; }
make install > /tmp/fs-install.log 2>&1
make samples > /tmp/fs-samples.log 2>&1      # default config into /etc/freeswitch
make sounds-en-us-callie-16000 > /tmp/fs-sounds.log 2>&1 || echo "sound pack skipped (optional)"

echo "== 5. Service user and systemd unit"
id freeswitch >/dev/null 2>&1 || useradd --system --home /var/lib/freeswitch --shell /usr/sbin/nologin freeswitch
mkdir -p /var/lib/freeswitch/fs-switch-voicemail /var/log/freeswitch /var/lib/freeswitch/tls
chown -R freeswitch:freeswitch /etc/freeswitch /var/lib/freeswitch /var/log/freeswitch /var/run/freeswitch 2>/dev/null || true
cat > /etc/systemd/system/freeswitch.service <<'UNIT'
[Unit]
Description=FreeSWITCH
After=network.target

[Service]
Type=simple
User=freeswitch
Group=freeswitch
ExecStart=/usr/bin/freeswitch -nonat -nf -u freeswitch -g freeswitch
ExecReload=/usr/bin/fs_cli -x reloadxml
Restart=always
LimitCORE=infinity
LimitNOFILE=100000

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload 2>/dev/null || echo "systemd not running here; unit file written, enable it on the server"

echo "== 6. Verify the modules we need are present"
/usr/bin/freeswitch -version
ls /usr/lib/freeswitch/mod/ | grep -E "mod_callcenter|mod_xml_curl|mod_sofia|mod_event_socket|mod_dptools|mod_voicemail|mod_opus" || { echo "missing modules"; exit 1; }
echo BUILD_DONE
