#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$root"

assert_file() {
  [[ -f "$1" ]] || { echo "missing file: $1" >&2; exit 1; }
}

for file in \
  .devcontainer/Dockerfile \
  .devcontainer/ssh-agent.Dockerfile \
  .devcontainer/compose.yml \
  .devcontainer/devcontainer.json \
  .devcontainer/daemon.json \
  .devcontainer/entrypoint.sh \
  .devcontainer/bashrc \
  .devcontainer/rootless-dockerd \
  .devcontainer/mise.toml \
  .devcontainer/prepare-mounts \
  .devcontainer/prepare-mounts.py \
  .devcontainer/prepare_mounts/__init__.py \
  .devcontainer/prepare_mounts/errors.py \
  .devcontainer/prepare_mounts/ports.py \
  .devcontainer/prepare_mounts/models/__init__.py \
  .devcontainer/prepare_mounts/models/dns.py \
  .devcontainer/prepare_mounts/models/mount.py \
  .devcontainer/prepare_mounts/models/paths.py \
  .devcontainer/prepare_mounts/models/repository.py \
  .devcontainer/prepare_mounts/resolver.py \
  .devcontainer/prepare_mounts/allowlist.py \
  .devcontainer/prepare_mounts/compose.py \
  .devcontainer/prepare_mounts/writer.py \
  .devcontainer/prepare_mounts/application.py \
  .devcontainer/prepare_mounts/cli.py \
  .devcontainer/allowlist.tsv \
  README.md \
  LICENSE \
  tests/test_prepare_mounts.py \
  tests/render_safe_fixture.py; do
  assert_file "$file"
done

for file in .codex/config.toml .claude/settings.json; do
  if [[ -e "$file" ]]; then
    echo "project agent configuration must not be checked in: $file" >&2
    exit 1
  fi
done

if rg -n '/var/run/docker.sock' .devcontainer/compose.yml .devcontainer/devcontainer.json; then
  echo "the Devcontainer must not mount the outer Docker socket" >&2
  exit 1
fi

bash -n .devcontainer/entrypoint.sh .devcontainer/prepare-mounts .devcontainer/rootless-dockerd

command -v python3 >/dev/null 2>&1 || {
  echo 'python3 is required for the host-side allowlist preparation' >&2
  exit 1
}
python3 -c 'import json, pathlib; path = pathlib.Path(".devcontainer/devcontainer.json"); text = "\n".join(line for line in path.read_text().splitlines() if not line.lstrip().startswith("//")); json.loads(text)'
python3 -m json.tool .devcontainer/daemon.json >/dev/null
python3 -m unittest discover -s tests -p 'test_*.py'

rg -q 'NoNewKeyring' .devcontainer/daemon.json
rg -q 'docker-buildx-plugin' .devcontainer/Dockerfile
if rg -n '^ARG MISE_VERSION=' .devcontainer/Dockerfile; then
  echo 'mise must track the latest stable release instead of a fixed version' >&2
  exit 1
fi
rg -q 'https://mise\.run' .devcontainer/Dockerfile
rg -q 'MISE_INSTALL_ARCH="\$\{mise_arch\}"' .devcontainer/Dockerfile
rg -q 'MISE_INSTALL_PATH=/usr/local/bin/mise' .devcontainer/Dockerfile
rg -q '^node = "lts"$' .devcontainer/mise.toml
rg -q '^"npm:@openai/codex" = "latest"$' .devcontainer/mise.toml
rg -q '^"npm:@anthropic-ai/claude-code" = "latest"$' .devcontainer/mise.toml
for tool in rg fd jq yq ast-grep gh tmux; do
  rg -q "^${tool} = \"latest\"$" .devcontainer/mise.toml
done
rg -q '^# dev_sandbox$' README.md
rg -q '\[MIT License\]\(LICENSE\)' README.md
rg -q 'devcontainer up --workspace-folder \.' README.md
rg -q 'Dev Containers: Reopen in Container' README.md
rg -q 'Project: Open Remote' README.md
rg -q '^MIT License$' LICENSE
rg -q 'source: mise-data' .devcontainer/compose.yml
rg -q 'target: /home/dev/.local/share/mise' .devcontainer/compose.yml
rg -q 'nocopy: false' .devcontainer/compose.yml
rg -q '^  mise-data:$' .devcontainer/compose.yml
if awk '
  /^  docker:$/ { service = "docker"; next }
  /^  [[:alnum:]_-]+:$/ { service = "" }
  service == "docker" && /mise-data/ { found = 1 }
  END { exit found ? 0 : 1 }
' .devcontainer/compose.yml; then
  echo 'mise-data must not be mounted into the Docker daemon container' >&2
  exit 1
fi
if rg -n 'postCreateCommand.*mise-install-allowed' .devcontainer/devcontainer.json; then
  echo 'mise-install-allowed must not run during Devcontainer startup' >&2
  exit 1
fi
rg -q '/etc/profile.d/mise.sh' .devcontainer/Dockerfile
rg -q 'COPY \.devcontainer/bashrc /home/dev/\.bashrc' .devcontainer/Dockerfile
if rg -n 'mise-project-tools|mise-install-allowed|mise_project_tools_' .devcontainer; then
  echo 'project-specific mise automation must not be part of the Devcontainer' >&2
  exit 1
fi
rg -q 'DOCKER_CONFIG' .devcontainer/Dockerfile .devcontainer/compose.yml
if rg -n 'ROOTLESS_DOCKER_DNS:' .devcontainer/compose.yml; then
  echo 'the base Compose file must not inject an unvalidated host DNS override' >&2
  exit 1
fi
rg -q 'socat' .devcontainer/ssh-agent.Dockerfile
rg -q 'ROOTLESS_DOCKER_DNS' .devcontainer/compose.yml .devcontainer/rootless-dockerd
rg -q 'unix:///docker-socket/docker.sock' .devcontainer/Dockerfile .devcontainer/compose.yml
rg -q 'socket_path="\$socket_dir/docker.sock"' .devcontainer/rootless-dockerd
rg -q -- '--host="unix://\$socket_path"' .devcontainer/rootless-dockerd
rg -q 'target: /docker-socket' .devcontainer/compose.yml
rg -q 'class DnsServers' .devcontainer/prepare_mounts/models/dns.py
rg -q 'class ContainerMountPath' .devcontainer/prepare_mounts/models/mount.py
rg -q 'from prepare_mounts.cli import main' .devcontainer/prepare-mounts.py
rg -q 'ROOTLESS_DOCKER_DNS' .devcontainer/prepare_mounts/models/dns.py
rg -q 'scutil' .devcontainer/prepare_mounts/resolver.py
rg -q 'resolvectl' .devcontainer/prepare_mounts/resolver.py
rg -q 'ROOTLESS_DOCKER_DNS is required' .devcontainer/rootless-dockerd
rg -q -- '--dns' .devcontainer/rootless-dockerd
rg -q '^    healthcheck:' .devcontainer/compose.yml
rg -q 'name=rootless' .devcontainer/compose.yml
rg -q 'condition: service_healthy' .devcontainer/compose.yml .devcontainer/prepare_mounts/compose.py
rg -q '"updateRemoteUserUID": false' .devcontainer/devcontainer.json
rg -q 'docker.pid' .devcontainer/rootless-dockerd
rg -q 'DOCKERD_ROOTLESS_ROOTLESSKIT_STATE_DIR' .devcontainer/rootless-dockerd
rg -q '/tmp/devcontainer-dockerd-rootless' .devcontainer/rootless-dockerd
rg -q 'SSH_AUTH_SOCK' .devcontainer/prepare_mounts/allowlist.py .devcontainer/prepare_mounts/application.py
rg -q '/run/host-ssh-agent.sock' .devcontainer/prepare_mounts/compose.py
if command -v rg >/dev/null 2>&1; then
  if rg -n --hidden \
    --glob '!tests/validate.sh' \
    --glob '!.git/**' \
    '(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|ANTHROPIC_API_KEY=|OPENAI_API_KEY=)' \
    .; then
    echo "possible credential found in tracked configuration" >&2
    exit 1
  fi
fi

validation_fixture_dir=$(mktemp -d /tmp/devcontainer-validation.XXXXXX)
trap 'rm -rf -- "$validation_fixture_dir"' EXIT
safe_override="$validation_fixture_dir/compose.safe.yml"
safe_ssh_override="$validation_fixture_dir/compose.safe-ssh.yml"

# Never invoke the production prepare-mounts command here. It reads the user's
# allowlist and can place resolved host paths or SSH socket paths in output.
python3 tests/render_safe_fixture.py \
  "$safe_override" "$validation_fixture_dir"
python3 tests/render_safe_fixture.py \
  "$safe_ssh_override" "$validation_fixture_dir" --ssh-agent

if rg -q '^  ssh-agent:' "$safe_override"; then
  echo 'the SSH relay must be opt-in' >&2
  exit 1
fi
if awk '/^  workspace:/{inside=1; next} inside && /^  [A-Za-z0-9_-]+:/{exit} inside' \
  "$safe_ssh_override" | rg -q '/run/host-ssh-agent.sock'; then
  echo 'the host SSH agent must not be mounted directly into the workspace' >&2
  exit 1
fi
if awk '/^  docker:/{inside=1; next} inside && /^  [A-Za-z0-9_-]+:/{exit} inside' \
  "$safe_ssh_override" | rg -q '/run/host-ssh-agent.sock'; then
  echo 'the host SSH agent must not be mounted into the Docker daemon container' >&2
  exit 1
fi
if command -v docker >/dev/null 2>&1; then
  docker compose \
    -f .devcontainer/compose.yml \
    -f "$safe_override" \
    config --quiet
  docker compose \
    -f .devcontainer/compose.yml \
    -f "$safe_ssh_override" \
    config --quiet
fi

echo "validation passed"
