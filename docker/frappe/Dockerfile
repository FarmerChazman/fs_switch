# Frappe v16 bench for the FS Switch app. Built from the repository root.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git wget xz-utils build-essential pkg-config \
      libffi-dev libssl-dev libmariadb-dev mariadb-client redis-tools redis-server \
      libjpeg-dev fontconfig libxrender1 cron \
    && rm -rf /var/lib/apt/lists/*

# Node 24 is used for the Vue/Vite build.
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g yarn@1.22.22 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN useradd -m -u 1001 -s /bin/bash frappe
USER frappe
ENV HOME=/home/frappe \
    PATH=/home/frappe/venv/bin:/home/frappe/.local/bin:$PATH \
    FS_SWITCH_ROOT=/home/frappe/fs-switch \
    FS_SWITCH_BENCH=/home/frappe/fs-switch-bench \
    FS_SWITCH_PYTHON=3.14 \
    FS_SWITCH_VENV=/home/frappe/venv

WORKDIR /home/frappe/fs-switch
COPY --chown=frappe:frappe . /home/frappe/fs-switch
RUN mkdir -p /home/frappe/fs-switch/logs \
    && bash setup_bench.sh \
    && cd /home/frappe/fs-switch/apps/fs_switch/frontend \
    && npm ci --no-audit --no-fund \
    && npm run build

EXPOSE 8000 9000
ENTRYPOINT ["bash", "/home/frappe/fs-switch/docker/frappe/entrypoint.sh"]
