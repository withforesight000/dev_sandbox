# Security model

[日本語版](security-model.ja.md)

This document describes what the Dev Container boundary is intended to limit,
what remains visible to an AI agent, and which deployment assumptions still
require trust. It is a repository-exposure boundary, not a complete substitute
for a microVM or a deny-by-default network policy.

## Security goals

The normal setup is designed to keep unrelated host data out of the agent's
filesystem while retaining a usable Dev Container and an inner rootless Docker
daemon. The Dev Containers client mounts the current repository into the
`workspace` service. Each additional repository is selected in
`.devcontainer/allowlist.tsv` together with its container destination; an
`@workspace` row can also add the current repository to the generated mounts,
including the `docker` service.

Changing a repository's container destination only organizes its in-container
view. It does not reduce the access the agent has to that repository's files.
The configured destination is used directly; no navigation alias is generated.
For nested destinations under `/workspaces`, synthetic parent directories are
ephemeral `tmpfs` mounts and do not expose a host parent directory.

Host-side preparation resolves the allowlist and writes generated Compose
configuration containing the selected host source paths. Repository test and
validation scripts, including `tests/validate.sh`, must therefore use synthetic
temporary repositories with neutral names such as `repo-alpha` and `repo-beta`.
They must not run the production preparation command against a user's personal
allowlist or publish its generated output.

## What this protects

Additional repository paths listed in `.devcontainer/allowlist.tsv` are mounted
at the container destinations specified in each row. The normal setup does not
mount:

- the host home directory;
- SSH key files or cloud credentials;
- host Docker configuration files or the outer Docker socket;
- arbitrary parent directories containing multiple repositories.

The allowlist is checked before Compose starts. Missing paths, non-repository
paths, nested paths, duplicate entries, duplicate or nested container
destinations, malformed rows, and invalid destinations fail closed. Every
additional repository must be a Git repository root, and every row must
specify an absolute container destination. The current repository referenced by
`@workspace` is the deliberate exception to the additional-repository Git-root
check.

## What this does not protect

Every allowlisted repository is inside the agent's trust boundary. The agent
can read, write, delete, and execute everything there, including hidden files,
Git hooks, build scripts, and local configuration. Keep the list minimal and
do not allowlist repositories containing secrets that the agent should not
handle.

The agent can control the inner rootless Docker daemon and create containers or
mount paths that are already visible inside the Dev Container. Rootless Docker
is a stronger boundary, not an absolute security guarantee. Kernel
vulnerabilities, misconfigured privileged operations, or newly added host
mounts can weaken the boundary.

The allowlist does not restrict network access, the behavior of processes in
allowlisted repositories, or the contents of containers created by the inner
daemon when they can see an allowlisted path. Docker Desktop File Sharing on
macOS must also be restricted to the current repository and the additional
repositories actually used; sharing a broad home-directory parent undermines
the intended host-side boundary.

## Trust assumptions

### Outer container runtime

The Docker daemon container is `privileged` at the outer container-runtime
level because RootlessKit needs namespace setup support. The daemon itself and
the containers it creates run as the unprivileged `dev` user. The outer Docker
socket is not mounted into the workspace, and the daemon container receives
only the explicitly allowlisted repository paths. Its data root and Unix
socket are isolated in named volumes.

The outer container runtime, the host kernel, the privileged `docker` service,
the Dev Container image, and any additional host mounts remain deployment trust
assumptions. Keep the image and the Docker Desktop or Linux host patched.

### Existing repository workflows

An existing repository may request `privileged`, `SYS_PTRACE`, or a Docker
socket mount for development helpers. Under this setup,
`/var/run/docker.sock` resolves to the inner rootless socket through a
compatibility symlink; it does not reach the outer daemon. Each repository's
Compose workflow must still be tested. A workflow that genuinely requires the
outer daemon is not compatible with this boundary.

### Network access

This project does not provide Docker Sandboxes' deny-by-default outbound
network policy. Treat external network access as a separate trust concern and
do not assume that repository allowlisting limits what the agent can send to
external services.

## Agent state and credentials

This repository does not check in Codex or Claude project settings.
Authentication and mutable per-developer state are stored in named volumes.
Never bind-mount the host's agent home directory or SSH key files into this
container.

For private Git dependencies, the host SSH agent can be explicitly forwarded by
setting `SSH_AUTH_SOCK` before starting or reopening the Dev Container.
`prepare-mounts` validates that the value is an absolute Unix socket and
generates a bind mount for a dedicated relay service. The workspace receives
the agent protocol, not private key files; the privileged `docker` service does
not receive this socket.

Forwarding an SSH agent still grants every process in the workspace container
the ability to ask it to authenticate with keys currently loaded in the
agent. Use a dedicated development or deploy key with the smallest repository
permissions needed. Do not use an agent containing production,
administrator, or unrelated personal keys. If `SSH_AUTH_SOCK` is unset, no
agent mount is generated; if it is set but invalid, startup fails closed with
an actionable error.

## Related comparison

For the trade-offs against Docker Sandboxes' microVM, credential proxy, and
network isolation model, see the comparison in the [main README](../README.md).
