# FreeSWITCH 1.10.12 built from source, with the FS Switch config templates.
# Built from the repository root (see docker-compose.yml). The first build takes
# 30-60 minutes; later builds use the Docker layer cache.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8
COPY freeswitch /opt/fs-switch/freeswitch
RUN apt-get update && apt-get install -y --no-install-recommends openssl \
    && bash /opt/fs-switch/freeswitch/install/build-freeswitch.sh \
    && rm -rf /var/lib/apt/lists/*
COPY docker/freeswitch/entrypoint.sh /usr/local/bin/fs-switch-freeswitch-entrypoint
RUN chmod +x /usr/local/bin/fs-switch-freeswitch-entrypoint
# SIP 5060 (udp/tcp), WebRTC 5066/7443, RTP 16384-16484
EXPOSE 5060/udp 5060/tcp 5066 7443 16384-16484/udp
ENTRYPOINT ["/usr/local/bin/fs-switch-freeswitch-entrypoint"]
