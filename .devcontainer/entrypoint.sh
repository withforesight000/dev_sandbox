#!/usr/bin/env bash
set -euo pipefail

alias_file=/run/devcontainer/allowlist.tsv
workspace_dir=/workspaces

if [[ ! -r "$alias_file" ]]; then
  echo "devcontainer: missing generated allowlist at $alias_file" >&2
  exit 1
fi

mkdir -p "$workspace_dir"

while IFS=$'\t' read -r alias target extra; do
  [[ -z "${alias//[[:space:]]/}" ]] && continue
  [[ "$alias" == \#* ]] && continue
  if [[ -n "${extra:-}" || -z "${target:-}" || "$target" != /* || "$target" == "/" ]]; then
    echo "devcontainer: invalid alias row for '$alias'" >&2
    exit 1
  fi

  alias_path="$workspace_dir/$alias"
  if [[ -e "$alias_path" && ! -L "$alias_path" ]]; then
    if [[ "$alias_path" != "$target" ]]; then
      echo "devcontainer: refusing to replace existing path $alias_path" >&2
      exit 1
    fi
  fi
  if [[ -L "$alias_path" ]]; then
    current_target=$(readlink "$alias_path")
    if [[ "$current_target" != "$target" ]]; then
      echo "devcontainer: alias target changed for $alias" >&2
      exit 1
    fi
  else
    [[ -d "$target" ]] || {
      echo "devcontainer: missing mounted repository at $target" >&2
      exit 1
    }
    if [[ "$alias_path" != "$target" ]]; then
      ln -s "$target" "$alias_path"
    fi
  fi
done < "$alias_file"

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
