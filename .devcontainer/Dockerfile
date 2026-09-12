FROM ubuntu:26.04

ARG TARGETARCH

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    HOME=/home/dev \
    XDG_CONFIG_HOME=/home/dev/.config \
    XDG_STATE_HOME=/home/dev/.local/state \
    MISE_DATA_DIR=/home/dev/.local/share/mise \
    DOCKER_HOST=unix:///docker-socket/docker.sock \
    XDG_RUNTIME_DIR=/run/user/1000 \
    PATH=/home/dev/.local/share/mise/shims:/home/dev/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# bubblewarp for one of codex sandbox prerequisites
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        autoconf \
        bash \
        bison \
        bubblewrap \
        build-essential \
        ca-certificates \
        curl \
        dbus-user-session \
        fuse-overlayfs \
        git \
        iproute2 \
        iptables \
        libffi-dev \
        libgdbm-dev \
        liblzma-dev \
        libncurses-dev \
        libreadline-dev \
        libssl-dev \
        libyaml-dev \
        openssh-client \
        pkg-config \
        rustc \
        slirp4netns \
        tzdata \
        uuid-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Docker and its rootless runtime. The daemon is started inside this
# container; the outer Docker Desktop/Linux daemon socket is never mounted.
RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && source /etc/os-release \
    && printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' \
        "$(dpkg --print-architecture)" "$VERSION_CODENAME" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        docker-ce \
        docker-ce-cli \
        docker-buildx-plugin \
        docker-ce-rootless-extras \
        docker-compose-plugin \
        uidmap \
    && rm -rf /var/lib/apt/lists/*

# The official installer resolves the latest stable mise release at image
# build time and verifies its checksum before installing it.
RUN case "${TARGETARCH}" in \
        amd64) mise_arch=x64 ;; \
        arm64) mise_arch=arm64 ;; \
        *) echo "unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl -fsSL https://mise.run \
        | MISE_INSTALL_ARCH="${mise_arch}" MISE_INSTALL_PATH=/usr/local/bin/mise sh \
    && mise --version

RUN existing_user="$(getent passwd 1000 | cut -d: -f1 || true)" \
    && if [[ -n "$existing_user" && "$existing_user" != "dev" ]]; then \
         userdel --remove "$existing_user" 2>/dev/null || userdel "$existing_user"; \
       fi \
    && useradd --create-home --shell /bin/bash --uid 1000 dev \
    && printf 'dev:100000:65536\n' >> /etc/subuid \
    && printf 'dev:100000:65536\n' >> /etc/subgid \
    && install -d -o dev -g dev /home/dev/.config/mise \
    && install -d -o dev -g dev /home/dev/.config/docker \
    && install -d -o dev -g dev /home/dev/.config/docker-cli \
    && install -d -o dev -g dev /home/dev/.local/share/mise \
    && install -d -o dev -g dev /home/dev/.local/share/docker \
    && install -d -o dev -g dev /home/dev/.local/state/mise/trusted-configs \
    && install -d -o dev -g dev /home/dev/.local/state/mise/tracked-configs \
    && install -d -o dev -g dev /home/dev/.cache/mise \
    && install -d -o dev -g dev /home/dev/.codex \
    && install -d -o dev -g dev /home/dev/.claude \
    && install -d -o dev -g dev -m 0700 /run/user/1000 \
    && install -d -o dev -g dev -m 0700 /docker-socket \
    && install -d -o dev -g dev /workspaces \
    && if [[ ! -e /var/run/docker.sock && ! -L /var/run/docker.sock ]]; then ln -s /docker-socket/docker.sock /var/run/docker.sock; fi \
    && chown -R dev:dev /home/dev

COPY .devcontainer/mise.toml /home/dev/.config/mise/config.toml
RUN chown dev:dev /home/dev/.config/mise/config.toml

COPY .devcontainer/entrypoint.sh /usr/local/bin/devcontainer-entrypoint
COPY .devcontainer/rootless-dockerd /usr/local/bin/rootless-dockerd
COPY .devcontainer/bashrc /home/dev/.bashrc
COPY .devcontainer/daemon.json /home/dev/.config/docker/daemon.json
RUN chmod 0755 /usr/local/bin/devcontainer-entrypoint /usr/local/bin/rootless-dockerd \
    && { \
         printf '[[ -n "${MISE_DEVCONTAINER_PROFILE_LOADED:-}" ]] && return 0\n'; \
         printf 'export MISE_DEVCONTAINER_PROFILE_LOADED=1\n'; \
         printf 'eval "$(mise activate bash)"\n'; \
       } > /etc/profile.d/mise.sh \
    && chmod 0644 /etc/profile.d/mise.sh \
    && printf '\nif [[ $- == *i* && -r /etc/profile.d/mise.sh ]]; then\n  source /etc/profile.d/mise.sh\nfi\n' >> /etc/bash.bashrc \
    && chown dev:dev /home/dev/.bashrc /home/dev/.config/docker/daemon.json

USER dev
WORKDIR /

RUN MISE_YES=1 mise install

# mise's npm backend intentionally does not rely on package postinstall
# scripts. Claude Code needs its platform-native helper installed explicitly.
RUN claude_installer="$(find /home/dev/.local/share/mise/installs/npm-anthropic-ai-claude-code \
        -path '*/@anthropic-ai/claude-code/install.cjs' -print -quit)" \
    && [[ -n "$claude_installer" ]] \
    && node "$claude_installer"

ENTRYPOINT ["/usr/local/bin/devcontainer-entrypoint"]
CMD ["sleep", "infinity"]
