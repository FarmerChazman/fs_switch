# FreeSWITCH for FS Switch

This directory contains the FreeSWITCH-side pieces: a source build for Ubuntu
24.04, the XML-curl gateway config, the WebRTC SIP profile and a carrier gateway
template. The application logic lives in `apps/fs_switch`; this is only the voice
engine configuration.

## Docker

The root `docker-compose.yml` builds `docker/freeswitch/Dockerfile`, which runs
`install/build-freeswitch.sh` and then starts FreeSWITCH with
`docker/freeswitch/entrypoint.sh`. The entrypoint writes the config from the
container environment, so there are no secrets in the image.

Required variables:

- `FS_SWITCH_XML_CURL_SECRET` — must match the Frappe setting.
- `FS_SWITCH_ESL_PASSWORD` — must match the Frappe setting.
- `FS_SWITCH_PUBLIC_IP` — media address advertised to clients.
- `FS_SWITCH_SIP_DOMAIN` — SIP domain; defaults to `localhost`.
- `FRAPPE_URL` — internal Frappe URL, e.g. `http://frappe:8000`.

Optional carrier variables: `FS_SWITCH_TRUNK_PROXY`, `FS_SWITCH_TRUNK_USERNAME`,
`FS_SWITCH_TRUNK_PASSWORD`, `FS_SWITCH_TRUNK_REALM`. When the proxy is set the
entrypoint writes `/etc/freeswitch/sip_profiles/external/carrier.xml`.

## Manual install on Ubuntu 24.04

```bash
sudo bash install/build-freeswitch.sh
sudo bash install/install-config.sh
```

`build-freeswitch.sh` builds FreeSWITCH 1.10.12 (and the required sofia-sip and
spandsp versions) from source. It takes roughly 30–60 minutes on a 2-core host.
`install-config.sh` enables `mod_xml_curl` and `mod_callcenter`, installs the
configs and starts the service.

Then set the XML-curl URL and secret in
`/etc/freeswitch/autoload_configs/xml_curl.conf.xml`. The URL must be reachable
from the FreeSWITCH host and must end with:

```text
/api/method/fs_switch.api.xml_curl?secret=<the same secret as Frappe>
```

## Ports

| Port | Purpose |
|---|---|
| 5060/udp, 5060/tcp | SIP |
| 5066 | browser WebSocket (`ws://`) |
| 7443 | secure WebSocket (`wss://`) |
| 8021 | ESL (keep private) |
| 16384–16484/udp | RTP |

Use `ws://localhost:5066` for local development. Use `wss://` with a trusted
certificate in production; the container generates a self-signed certificate
only so local development can start.

## Notes

- `mod_xml_curl` fetches the directory, dialplan and `callcenter.conf` from
  Frappe. Editing documents in the console is enough; run `reloadxml` for
  configuration that FreeSWITCH caches.
- The `webrtc` profile owns ports 5066/7443. The stock `internal` profile also
  binds them, so the install/entrypoint comments those parameters out.
- The ESL port is not published by the Docker compose file.
