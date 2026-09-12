# Documentation synchronization

Use this playbook when changing `README.md`, `README.ja.md`, or any paired
document under `docs/`. Keep the two languages synchronized in meaning without
making the Japanese version a word-for-word translation.

## Document pairs and language rules

- `README.md` is English except for the Japanese README link near the top.
- `README.ja.md` is Japanese.
- `docs/usage.md` ↔ `docs/usage.ja.md`
- `docs/security-model.md` ↔ `docs/security-model.ja.md`
- Links from the English README point to English documents. Links from the
  Japanese README point to Japanese documents.
- Each paired document links to its counterpart. Keep headings, examples,
  warnings, and link targets aligned between the pair.

## Editorial principles

- Lead with the repository's purpose: expose only the repositories an AI agent
  needs, rather than the host as a whole.
- Describe the allowlist as a reviewed, repository-scoped access policy. Make
  clear that host source paths and container destinations are separate, and
  that destinations are organizational rather than additional security
  boundaries.
- State the security trade-off near the benefit: allowlisted repositories are
  read-write and their hidden files, hooks, scripts, and local configuration
  are inside the agent's trust boundary.
- Describe `workspace`, `docker`, and `ssh-agent` by their roles. Use
  `Dev Container`, `RootlessKit`, `workspace`, `docker`, `ssh-agent`,
  `allowlist`, and `SSH agent` consistently.
- Do not use informal architecture labels or claim that this project alone can
  use multiple repositories, one running environment, configuration files, or
  explicit mount paths.
- In comparisons with Docker Sandboxes, acknowledge their parent-workspace,
  additional-workspace, and experimental `sbxenv.yaml` options. Present this
  project's distinction as selective, policy-driven repository exposure and
  Dev Container / Compose integration, not stronger isolation. Mention Docker
  Sandboxes' microVM, credential-proxy, and deny-by-default network properties
  when relevant.

## Editing workflow

1. Read both files in the pair and the relevant usage/security documents before
   editing. Check the implementation when a sentence describes behavior.
2. Update the English and Japanese documents together. Preserve code
   identifiers, paths, commands, and configuration syntax exactly unless the
   implementation also changes.
3. Keep technical distinctions explicit:
   - the current repository is automatically mounted into `workspace`;
   - `@workspace` can add it to generated mounts, including `docker`;
   - generated aliases exist only in `workspace`;
   - Compose relative bind sources use the configured destination itself.
4. Verify that every relative link resolves, code fences are balanced, and the
   paired documents have the same heading-level sequence.
5. Run `bash tests/validate.sh` after documentation changes that accompany
   configuration or security-sensitive changes. Otherwise, run the relevant
   local checks and report what was and was not verified.

## Review checklist

- Does the text explain what data is excluded from the agent by default?
- Does it state what remains exposed once a repository is allowlisted?
- Does it avoid implying that mount-path organization provides isolation?
- Does it distinguish static/local validation from live runtime evidence?
- Do README language-specific links and document counterpart links point to the
  correct files?
- Are Japanese terms natural while keeping service names and identifiers
  unchanged?
