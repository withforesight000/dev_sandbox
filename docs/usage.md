# Usage

[日本語版](usage.ja.md)

This guide explains how to select repositories, start the Dev Container, and
use its tools without changing the project configuration of the repositories
you expose.

## Configure repository access

Add one explicit repository per row to `.devcontainer/allowlist.tsv`:

```text
/absolute/path/to/repository<TAB>/container/mount/path
```

The `dev_sandbox` repository is the current workspace and does not need an
allowlist row for the standard setup. Add only the other repositories that the
agent should be able to access.

The Dev Containers client mounts the current repository into the `workspace`
service separately from the generated allowlist mounts. `@workspace` is a
special source specification for adding the current repository to the
allowlist-generated mounts; it is not required for normal workspace access. Add
an `@workspace` row when the current repository must also be mounted into the
`docker` service or when it needs an explicit destination for a Compose build
or bind source.

### Host source paths

An additional repository must be an existing Git repository root. Do not add a
broad parent directory containing multiple repositories. Host paths must be
absolute. You can use these special forms for the current workspace or a path
relative to it:

- `@workspace` resolves to the current repository's absolute path.
- `@workspace:/absolute/path/to/repository` names an explicit absolute path.
- `@workspace-relative:../org/repo` names a path relative to the current
  repository.

The paths are resolved and validated on the host before Compose starts. Missing
paths, non-repository paths, nested paths, and duplicate paths fail closed.

### Container destinations

The second column is mandatory and must be an absolute, normalized directory
path inside the containers. The filesystem root and `/workspaces` itself are
reserved. Destinations must be unique and must not be nested. The same
destination is used in the `workspace` service and the `docker` service, so a
repository can stay at its existing host location while appearing in an
organized layout inside both containers.

For example, repositories stored in unrelated host directories can be grouped
under predictable paths inside the Dev Container:

```text
/Users/you/work/client/api<TAB>/workspaces/api
/Volumes/team/shared-lib<TAB>/workspaces/shared-lib
```

The configured mount destination is the canonical repository path in both
services; no navigation aliases or additional symlinks are created. For nested
destinations under `/workspaces`, missing parent directories are provided as
ephemeral `tmpfs` mounts owned by `dev:dev`. These synthetic parents do not
expose a host parent directory.

The host running the Dev Containers client must provide `python3`. Allowlist
preparation uses only Python's standard library and does not require
third-party packages.

## Applying allowlist changes

After changing `.devcontainer/allowlist.tsv`, apply the change from a host
terminal at the repository root, not from a terminal attached to the Dev
Container:

```sh
bash .devcontainer/prepare-mounts
```

If this command fails, fix the allowlist and run it again; do not reopen or
recreate the container using the previous generated configuration. After it
succeeds, recreate the container so additions and removals are applied:

- CLI: `devcontainer up --workspace-folder . --remove-existing-container`.
- VS Code: run `Dev Containers: Rebuild Container`.
- Zed: close the remote project, run the CLI command above from the host, and
  reopen it with `Project: Open Remote`.

The Dev Containers client also runs this command through `initializeCommand`
during startup, but that hook does not replace explicit container recreation
when the mount policy changes. The command regenerates
`.devcontainer/compose.allowlist.local.yml`; this file is ignored and must not
be committed or hand-edited. An allowlist-only change does not require an image
rebuild. For image or Compose changes, use the rebuild command supported by
your client; check the installed Dev Containers CLI options with
`devcontainer up --help` rather than assuming a `--build` option.

On Docker Desktop, grant File Sharing access to each newly added repository
before recreating the container. Share the repository path itself, not a broad
parent directory.

After reconnecting, verify the configured destinations from the workspace
terminal. For example, with the CLI:

```sh
devcontainer exec --workspace-folder . bash -lc \
  'test -d /workspaces/<destination> && ls -ld /workspaces/<destination>'
```

Also verify that destinations removed from the allowlist are no longer present.

## Runtime versions

The image installs the latest stable `mise` release at build time and uses
`.devcontainer/mise.toml` as its image-level tool manifest. The image includes
the latest Node.js LTS, Codex, Claude Code, and the baseline command-line tools
listed in that file. Entries using `latest` are resolved when the image is
built, so rebuild the Dev Container to receive newer releases.

Installed tools are persisted in the Docker-managed `mise-data` named volume;
the download cache is kept in the separate `mise-cache` volume. Neither volume
is stored in this repository. An empty `mise-data` volume is initialized from
the image, while subsequent image rebuilds do not overwrite an existing
volume.

Project tool versions and `mise` settings belong to each exposed repository.
The Dev Container does not inspect, install, or translate project
configuration automatically. Use the repository's normal workflow, for
example:

```bash
mise trust
mise install
mise current
```

The shell loads `mise`'s standard Bash activation, so trusted project
configuration is applied when you work in that repository. Run `mise upgrade`
explicitly when you want to update installed tools after an image rebuild.

## Agents and credentials

The image installs Codex and Claude Code through `mise`. Authentication and
other mutable agent state are stored in named volumes, not in this repository.
This project does not check in `.codex/config.toml` or `.claude/settings.json`,
and it does not override user configuration through launchers. Invoke `codex`
or `claude` normally and manage their settings as a user.

For builds that need private Git dependencies, configure a least-privilege
development key in the host SSH agent and start or reopen the Dev Container
with `SSH_AUTH_SOCK` exported. The startup script forwards only that Unix
socket to the `workspace` service through a dedicated relay; it does not mount
`~/.ssh` or forward the socket to the `docker` service. Check loaded identities
with `ssh-add -l`, and do not forward an agent containing production or
unrelated keys. Changing the agent socket requires reopening or rebuilding the
Dev Container.

## Docker and Compose

Docker commands use a rootless daemon in the dedicated `docker` service. Its
data directory and Unix socket are named volumes. The socket is mounted at
`/docker-socket/docker.sock`, outside RootlessKit's private `/run` copy-up
namespace. The outer Docker Desktop or Linux Docker Engine socket is not
mounted into the workspace.

The workspace Docker CLI uses `/home/dev/.config/docker-cli` as its client
configuration directory. If a private registry requires explicit
authentication, run `docker login` inside the Dev Container; credentials are
stored in the inner Docker CLI configuration.

Repositories are mounted at their configured container paths in both services.
The inner Docker daemon resolves bind sources from its own mount namespace, so
relative bind mounts in an existing Compose file must resolve from the same
configured path there. Run repository Compose workflows from that path.

## DNS for inner containers

The rootless daemon forwards usable upstream DNS servers to containers created
by the inner daemon. Host-side `prepare-mounts` detects them from the platform
resolver configuration: `scutil --dns` on macOS, and `/etc/resolv.conf` on
Linux. When Linux uses systemd-resolved, it reads the upstream configuration
from `/run/systemd/resolve/resolv.conf` before trying the optional
`resolvectl dns` fallback. Loopback and stub resolver addresses are not
forwarded because they are not reachable from the nested container namespace.
The address filter also rejects unspecified, multicast, link-local, and
reserved addresses. Host-side detection cannot prove that a resolver is
reachable from Docker's Linux VM, so a runtime DNS lookup is still required
when network reachability matters.

The `docker` service does not repeat host DNS discovery. It requires the
validated value generated by `prepare-mounts`; the base Compose file does not
pass the host variable directly. If automatic detection is not sufficient,
set `ROOTLESS_DOCKER_DNS` to a comma-separated list of resolver addresses
reachable from Docker's Linux VM before reopening the Dev Container:

```bash
export ROOTLESS_DOCKER_DNS=<reachable-dns-server>
```

Do not use a loopback address or a Docker embedded resolver address. On macOS,
Zed launched from Finder or the Dock may not inherit shell environment
variables; rely on automatic detection or launch the project from a shell with
the override exported.

## Troubleshooting

- If the rootless daemon does not start, inspect `docker compose logs docker`.
  A message about missing upstream DNS means host-side detection found no
  usable address; set `ROOTLESS_DOCKER_DNS` and reopen the Dev Container.
- If an inner build reports `Temporary failure resolving`, inspect the `docker`
  service log for the selected DNS servers and configure the override when
  automatic detection cannot find a reachable resolver.
- If an inner container fails with a session-keyring error, rebuild the image
  so the `NoNewKeyring` runtime configuration is installed. Do not work around
  this by increasing a host-wide kernel quota.
- On macOS, configure Docker Desktop File Sharing for the current repository
  and each explicitly allowlisted repository, not for a broad home-directory
  parent.
- If a repository has no Git metadata, it cannot be added to the allowlist.
- If a bind source is not visible at its configured container path, adjust the
  repository's Docker workflow. Do not mount a broad host parent as a workaround.
