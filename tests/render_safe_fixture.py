#!/usr/bin/env python3
"""Render Compose fixtures without reading the user's project allowlist."""

from __future__ import annotations

import sys
from pathlib import Path

DEVCONTAINER_PATH = Path(__file__).resolve().parents[1] / ".devcontainer"
sys.path.insert(0, str(DEVCONTAINER_PATH))

import prepare_mounts


def main(arguments: list[str]) -> int:
    """Render a synthetic allowlist override for validation."""

    if len(arguments) not in (2, 3):
        print(
            "usage: render_safe_fixture.py OUTPUT FIXTURE_ROOT [--ssh-agent]",
            file=sys.stderr,
        )
        return 2

    output = Path(arguments[0]).resolve()
    fixture_root = Path(arguments[1]).resolve()
    use_ssh_agent = len(arguments) == 3 and arguments[2] == "--ssh-agent"
    if len(arguments) == 3 and not use_ssh_agent:
        print("unknown option", file=sys.stderr)
        return 2

    repositories = []
    for name, target in (
        ("repo-alpha", "/workspaces/fixtures/repo-alpha"),
        ("repo-beta", "/workspaces/fixtures/repo-beta"),
    ):
        source = fixture_root / name
        source.mkdir(parents=True, exist_ok=True)
        repositories.append(
            prepare_mounts.AllowlistedRepository(source=source, target=target)
        )

    ssh_agent_socket = fixture_root / "ssh-agent.sock" if use_ssh_agent else None
    content = prepare_mounts.ComposeOverrideRenderer().render(
        repositories=repositories,
        repo_root=fixture_root,
        ssh_agent_socket=ssh_agent_socket,
        dns_servers=prepare_mounts.DnsServers.from_detected(["192.0.2.53"]),
    )
    output.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
