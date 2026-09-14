# Agent instructions

These instructions define the non-negotiable working boundary for this
repository. Preserve unrelated user changes, keep the security boundary
explicit, and do not trade away a restriction merely to make a workflow
easier.

## Scope and host-data boundary

- Work only in explicitly mounted repositories under `/workspaces`.
- Do not inspect or mount host paths outside those repositories.
- Never read or mount the host home directory, SSH key files, the `.ssh`
  directory, cloud credentials, Docker configuration, or the outer Docker
  socket.
- `SSH_AUTH_SOCK` is the only host-credential exception. It is opt-in and may
  be forwarded only through the dedicated SSH relay to the
  `workspace` service.
- Treat `.devcontainer/allowlist.tsv` as a reviewed access policy. Do not
  change it merely to bypass a restriction, and never replace it with a broad
  host-directory mount.
- Treat local changes to `.devcontainer/allowlist.tsv` as user-specific
  working state. Do not include those changes in commits; preserve them in the
  working tree and leave the tracked policy unchanged unless the user
  explicitly requests a policy update.
- Use the inner rootless Docker daemon for Docker commands. Do not recover,
  mount, or otherwise use the outer Docker Desktop or Linux Docker Engine
  socket.
- Do not use the inner Docker daemon to inspect paths outside the explicitly
  mounted repositories.

## Architecture invariants

- This repository provides a Dev Container sandbox with three separate roles:
  - `workspace` is the work container. The Dev Containers client mounts the
    current repository there automatically.
  - `docker` is the dedicated container that runs the rootless Docker daemon.
  - `ssh-agent` is an optional relay, created only when `SSH_AUTH_SOCK` is
    explicitly configured.
- Keep these roles and their security boundaries separate. Use explicit role
  names rather than informal architecture labels.
- Additional repositories are declared in `.devcontainer/allowlist.tsv`, one
  repository per row. Each row maps a host source path to a container
  destination. Additional sources must be existing Git repository roots; do
  not expose a broad parent directory containing multiple repositories.
- Container destinations must be absolute, normalized, non-root, unique, and
  non-nested. `/workspaces` itself is reserved. The same configured
  destination is mounted into both `workspace` and `docker`.
- The current repository does not need an allowlist row for normal
  `workspace` access. `@workspace` is a special allowlist source
  specification for adding it to generated mounts, including `docker`, or
  assigning it an explicit destination.
- Allowlisted repositories use their configured destinations directly in both
  `workspace` and `docker`; no navigation aliases are generated. Run Compose
  workflows from the configured destination when relative bind sources are
  involved.

## Required workflow

- For changes to `.devcontainer/`, allowlist handling, resolver behavior,
  nested Docker, or security-sensitive wiring, read
  `.agents/skills/devcontainer-maintenance/SKILL.md` before editing.
- For changes to README or paired documents under `docs/`, read
  `.agents/skills/documentation-sync/SKILL.md` before editing.
- Before opening or reopening the Dev Container, and after changing the
  allowlist or resolver configuration, run:

  ```bash
  bash .devcontainer/prepare-mounts
  ```

- `prepare-mounts` validates the policy before Compose starts and regenerates
  the ignored `.devcontainer/compose.allowlist.local.yml`. Never commit or
  hand-edit that file. The legacy `.devcontainer/allowlist.local.tsv` is not
  consumed by the current container startup path.

## Validation

- For changes to scripts, Python preparation code, Compose configuration,
  allowlist handling, or security-sensitive wiring, run:

  ```bash
  bash tests/validate.sh
  ```

- This is primarily local static, unit, and Compose-configuration validation.
  It does not prove live DNS connectivity, external network behavior, or every
  deployment-specific security property.
- Repository test and validation scripts, including `tests/validate.sh`, must
  use synthetic temporary fixtures with neutral names such as `repo-alpha` and
  `repo-beta`. Do not invoke the production `.devcontainer/prepare-mounts`
  command from those scripts: it reads the user's allowlist and its generated
  Compose or SSH-agent paths may contain sensitive host information.
- When runtime behavior matters and the Dev Container is running, follow the
  runtime checklist in
  `.agents/skills/devcontainer-maintenance/SKILL.md`: verify the daemon is rootless,
  perform an actual inner-container DNS lookup, and exercise a representative
  BuildKit/build path.

## Documentation and project settings

- Keep `README.md` in English except for the Japanese README link near the
  top. Keep `README.ja.md` in Japanese.
- Keep these documentation pairs synchronized in meaning, headings, examples,
  warnings, and links:
  - `docs/usage.md` ↔ `docs/usage.ja.md`
  - `docs/security-model.md` ↔ `docs/security-model.ja.md`
- Links from `README.md` must point to English documents. Links from
  `README.ja.md` must point to Japanese documents. Each paired document must
  link to its counterpart.
- Use `Dev Container`, `RootlessKit`, `workspace`, `docker`,
  `ssh-agent`, `allowlist`, and `SSH agent` consistently.
- Do not check in `.codex/config.toml` or `.claude/settings.json`. Agent
  settings and authentication state belong to the user, not this repository's
  tracked project configuration.

## Commit messages

- Write commit messages in English.
- Use this structure without exception:
  1. subject: one imperative, capitalized line ending with a period, about
     50–72 characters;
  2. one blank line;
  3. a prose body explaining the why and the policy, with design intent such
     as layer boundaries, wrapped at about 72–80 characters per line;
  4. one blank line;
  5. bullet points listing concrete changes with `- `, starting in lowercase
     and wrapped when necessary.
