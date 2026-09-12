# dev_sandbox

[日本語版 README](README.ja.md)

> Give an AI coding agent the repositories it needs—not your whole host.

`dev_sandbox` is a security-focused Dev Container for using AI coding agents such as Codex and Claude with selected local repositories. Its primary purpose is to keep unrelated host data and sensitive information out of the agent's reach while preserving a practical environment for inspecting code, running tests, and using Docker Compose.

The sandbox workspace is available to the agent. Additional repositories become available only when you explicitly add them to a fail-closed allowlist. In the normal setup, the host home directory, SSH keys, cloud credentials, Docker configuration, and host Docker socket are not mounted into the container.

## Why this exists

An AI agent is most useful when it can inspect the code, tools, and related repositories needed for a task. Giving it a broad host directory, however, makes the trust boundary difficult to see and audit. A typo in a mount path can expose much more than intended, and a repository often contains hidden files, build scripts, hooks, or local credentials that deserve the same care as source code.

This project makes the intended repository boundary explicit and reviewable:

- **Additional repositories are declared one per row** in `.devcontainer/allowlist.tsv`.
- **`prepare-mounts` validates the policy before the Dev Container starts.**
- Missing paths, non-repository paths, broad parent directories, nested or duplicate mounts, and invalid destinations fail closed.
- The same approved repository paths are mounted into the workspace and the dedicated container running the rootless Docker daemon, so relative Compose bind mounts resolve consistently.

The result is an ordinary Dev Container workflow with a separate rootless Docker daemon, rather than an opaque collection of agent-specific project settings. See the [Usage guide](docs/usage.md) and [Security Model](docs/security-model.md) for setup details, the complete boundary, and its assumptions.

## Key benefits

- **Task-scoped access** — expose only the repositories required for the current investigation or change.
- **Organized container paths** — keep repositories where they are on the host while mapping each selected Git repository to a chosen absolute path inside the containers. Repositories scattered across the host can be grouped under a predictable in-container layout; the mappings are reviewed and validated as part of the allowlist.
- **Cross-repository investigation** — inspect related services, clients, libraries, schemas, and infrastructure together to produce more grounded analysis and change-impact judgments.
- **Dev Container and Compose compatibility** — use standard container tooling and a dedicated rootless Docker daemon without handing the host Docker socket to the agent.
- **Familiar tools** — use `mise`, Codex, Claude, Docker Compose, VS Code, Zed, or the Dev Containers CLI in a normal workspace.
- **Explicit credential handling** — SSH agent forwarding is opt-in and relayed only to the workspace; host credential files are not mounted.

## Cross-repository investigation

Many engineering questions cross repository boundaries:

- an API repository and its client or frontend;
- a shared library and the services that consume it;
- schemas or generated code and their producers and consumers;
- an application repository and its deployment or infrastructure repository.

Allowlisting the smallest useful set lets an agent compare the actual implementations, contracts, and tests instead of guessing from one repository's documentation. That can improve repository-wide debugging, dependency investigation, design review, and change planning.

The allowlist keeps each host source path separate from its container destination. A repository can remain in its existing host location while appearing at an organized path such as `/workspaces/api` or `/workspaces/shared-lib` inside the Dev Container. This is an organizational convenience, not an additional security boundary: changing the container path does not change what the agent can access inside that repository.

This is an access trade-off, not a security guarantee. Every allowlisted repository is mounted read-write into both the workspace and the dedicated container running the rootless Docker daemon, and the agent may read or modify everything inside those repositories, including hidden files and local configuration. Keep the list minimal, review it as policy, and do not allowlist repositories that contain secrets you do not want the agent to handle.

## Security boundary

| Resource | Default behavior |
| --- | --- |
| Sandbox workspace | The current project is available to the agent |
| Additional repositories | Available only when explicitly listed in the allowlist |
| Allowlisted repositories | Mounted read-write into both the `workspace` container and the dedicated container running the rootless Docker daemon |
| Host home, SSH keys, and cloud credentials | Not mounted |
| Host Docker configuration and socket | Not mounted; containers use the inner rootless daemon |
| Host SSH agent | Forwarded only when `SSH_AUTH_SOCK` is explicitly configured, through a workspace-only relay |
| Outbound network | This repository does not provide a deny-by-default egress policy; treat network access as a separate trust concern |

In this setup, `workspace` is the work container, and the `docker` service is a separate container running the rootless Docker daemon. The `workspace` container runs as a non-privileged user with dropped capabilities and `no-new-privileges`. The `docker` service is privileged from the outer container runtime only as required to start its rootless daemon; this is an explicit trust assumption. The outer Docker socket is never mounted into the workspace.

### What this protects

- Unrelated host repositories and parent directories that are not allowlisted.
- Host home-directory data, SSH key files, cloud credential files, Docker configuration, and the outer Docker socket in the normal setup.
- Accidental expansion of the mount policy through missing, broad, nested, duplicate, or invalid entries.

### What this does not protect

- The workspace and every allowlisted repository are inside the agent's trust boundary. The agent can read, write, delete, and execute content there, including Git hooks and hidden files.
- The agent has control of the inner rootless Docker daemon and can create containers or mount paths that are visible inside that boundary.
- The outer container runtime, the privileged `docker` service used to run rootless Docker, the host kernel, and any additional host mounts remain part of the deployment's trust assumptions.
- SSH agent forwarding can authorize operations using keys available through the agent socket. Any workspace process can ask the relay to authenticate.
- This project does not provide Docker Sandbox's microVM boundary, credential proxy, or deny-by-default network policy.

## How it compares with Docker Sandboxes

See Docker's official [Sandboxes overview](https://docs.docker.com/ai/sandboxes/), [multiple workspaces](https://docs.docker.com/ai/sandboxes/usage/#multiple-workspaces), [environment files](https://docs.docker.com/ai/sandboxes/configuration/environment-files/), [security model](https://docs.docker.com/ai/sandboxes/security/), and [security defaults](https://docs.docker.com/ai/sandboxes/security/defaults/).

Both approaches can work across repositories. Docker Sandboxes can use a parent directory as the primary workspace, attach additional workspaces, and experimentally define workspaces through `sbxenv.yaml`. Therefore, multi-repository access, a single running sandbox, and configuration-file-based workspace definitions are not unique advantages of this project.

The difference is how repository exposure is modeled. This project treats repository access as a checked-in policy in `.devcontainer/allowlist.tsv`:

- each additional repository is declared explicitly with a host source path and a container destination;
- an unrelated sibling repository under the same host parent is not exposed unless it is listed;
- `prepare-mounts` rejects missing or non-Git paths, broad parent directories, nested or duplicate entries, and invalid container destinations before startup;
- approved repositories are mounted at explicit peer paths in both the `workspace` service and the `docker` service.

This lets an agent move between selected repositories such as `/workspaces/api` and `/workspaces/shared-lib` in one standard Dev Container without exposing every repository under a shared parent directory. Docker Sandboxes can provide similar navigation when the parent directory is chosen as the primary workspace or when additional workspaces are configured. The distinction is therefore selective, policy-driven source-to-destination mapping together with Dev Container and Compose integration—not exclusive support for multi-repository workflows.

Docker Sandboxes use a per-sandbox microVM as the primary trust boundary, provide a private Docker Engine and filesystem, proxy outbound TCP traffic with a deny-by-default policy, and can provide credentials through a host-side proxy rather than placing raw values in the VM. Those properties are a better fit when the strongest isolation for an autonomous or untrusted agent is the priority.

Choose this project when selective repository exposure and a familiar Dev Container / Compose workflow are the priority. Choose Docker Sandboxes when stronger VM-, network-, and credential-isolation defaults for an autonomous or untrusted agent are the priority.

## Prerequisites

- Docker Desktop on macOS, or Docker Engine on Linux.
- `python3` on the host for allowlist preparation.
- A Dev Containers-compatible client such as the Dev Containers CLI, VS Code, or Zed.
- File-sharing permission for only the allowlisted host paths when using Docker Desktop.

## Getting started

### 1. Configure the repository allowlist

Edit `.devcontainer/allowlist.tsv`. Each row contains a host repository path, a tab, and its absolute path inside the containers:

```text
/Users/you/src/api	/workspaces/api
/Users/you/src/shared-lib	/workspaces/shared-lib
```

Use repository roots, not a broad parent directory. Host paths must exist, be absolute, and be unique and non-nested. Container destinations must also be absolute, unique, and non-nested. The main workspace does not need an allowlist row. Use `@workspace` or `@workspace-relative` when a path should follow the current workspace:

```text
@workspace	/workspaces/current
@workspace-relative:../shared-lib	/workspaces/shared-lib
```

The final path component is used as the repository alias. Avoid aliases that collide with the workspace or another entry.

### 2. Start the Dev Container

Run from the repository root:

```sh
bash .devcontainer/prepare-mounts
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . bash
```

The Dev Container client also invokes `prepare-mounts` through `initializeCommand`. The script atomically regenerates ignored local files under `.devcontainer/`; do not commit or hand-edit them. Add `--build` to rebuild after changing the image or Compose configuration.

### 3. Choose your client

- CLI: install the [Dev Containers CLI](https://github.com/devcontainers/cli) and use the commands above.
- VS Code: install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) and run `Dev Containers: Reopen in Container`.
- Zed: use `Project: Open Remote` with this repository's Dev Container configuration.

## Daily use

Inside the workspace, use the repository's normal commands, for example:

```sh
mise install
mise run test
docker compose up
```

Codex and Claude can be invoked with their usual commands. Project-specific agent settings are intentionally user-owned; this repository does not prescribe `.codex/config.toml` or `.claude/settings.json`.

When using Docker or Compose, run from the configured container path. `DOCKER_HOST=unix:///docker-socket/docker.sock` points to the dedicated inner daemon. `/var/run/docker.sock` is only a compatibility symlink to that inner socket; it is not the host socket.

SSH access is optional. Configure `SSH_AUTH_SOCK` explicitly if the workspace needs the SSH agent, and understand that this permits authentication requests from processes in the workspace. Do not mount SSH key files or the host `.ssh` directory.

## Validation

Run the repository's validation suite from the repository root:

```sh
bash tests/validate.sh
```

This checks the allowlist preparation logic, unit behavior, and Compose configuration. It is primarily static and local validation; it does not prove live DNS connectivity, external network behavior, or every deployment-specific security property. After the Dev Container is running, validate the rootless daemon, an actual DNS lookup from an inner container, and a representative BuildKit/build path separately when those properties matter.

## Documentation

- [Usage guide](docs/usage.md)
- [Security model](docs/security-model.md)
- [Allowlist policy](.devcontainer/allowlist.tsv)
- [Dev Container configuration](.devcontainer/)

## License

[MIT License](LICENSE)
