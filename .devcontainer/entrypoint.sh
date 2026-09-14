#!/usr/bin/env bash
set -euo pipefail

workspace_dir=/workspaces

mkdir -p "$workspace_dir"

wait_for_rootless_docker() {
  local docker_host="${DOCKER_HOST:-}"
  local socket="${docker_host#unix://}"
  local security_options=''
  local last_error='Docker daemon was not reachable'

  for _ in {1..60}; do
    if [[ "$docker_host" != unix:///* ]]; then
      last_error="unsupported DOCKER_HOST: ${docker_host:-unset}"
    elif [[ ! -S "$socket" ]]; then
      last_error="Docker socket is not ready: $socket"
    elif security_options=$(docker info --format '{{json .SecurityOptions}}' 2>&1); then
      if [[ "$security_options" == *'"name=rootless"'* ]]; then
        return
      fi
      last_error="Docker daemon is reachable but not yet rootless: $security_options"
    else
      last_error="docker info failed: $security_options"
    fi
    sleep 1
  done

  echo "devcontainer: timed out waiting for a rootless Docker daemon" >&2
  echo "devcontainer: last rootless Docker check: ${last_error:-unavailable}" >&2
  exit 1
}

wait_for_rootless_docker

exec "$@"
