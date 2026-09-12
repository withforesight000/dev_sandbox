"""Compose override rendering for the Devcontainer services."""

from __future__ import annotations

from pathlib import Path

from .models import AllowlistedRepository, DnsServers


def yaml_quote(value: str) -> str:
    """Quote a scalar for the single-quoted YAML values in the override."""

    return "'" + value.replace("'", "''") + "'"


class ComposeOverrideRenderer:
    """Render the generated Compose override without external YAML packages."""

    def render(
        self,
        repositories: list[AllowlistedRepository],
        aliases: Path,
        repo_root: Path,
        ssh_agent_socket: Path | None,
        dns_servers: DnsServers | None = None,
    ) -> str:
        """Render workspace, Docker daemon, and optional SSH relay services."""

        lines = ["services:", "  workspace:"]
        self._append_workspace_service(lines, repositories, aliases, ssh_agent_socket)
        lines.append("  docker:")
        if dns_servers:
            lines.extend(
                [
                    "    environment:",
                    f"      ROOTLESS_DOCKER_DNS: {yaml_quote(dns_servers.as_environment_value())}",
                ]
            )
        lines.append("    volumes:")
        self._append_repository_mounts(lines, repositories)
        if ssh_agent_socket is not None:
            self._append_ssh_agent_service(lines, repo_root, ssh_agent_socket)
        return "\n".join(lines) + "\n"

    @staticmethod
    def _append_workspace_service(
        lines: list[str],
        repositories: list[AllowlistedRepository],
        aliases: Path,
        ssh_agent_socket: Path | None,
    ) -> None:
        if ssh_agent_socket is not None:
            lines.extend(
                [
                    "    environment:",
                    "      SSH_AUTH_SOCK: /run/ssh-agent/agent.sock",
                    "    depends_on:",
                    "      docker:",
                    "        condition: service_healthy",
                    "      ssh-agent:",
                    "        condition: service_healthy",
                ]
            )
        lines.append("    volumes:")
        if ssh_agent_socket is not None:
            lines.extend(
                [
                    "      - type: volume",
                    "        source: ssh-agent-socket",
                    "        target: /run/ssh-agent",
                ]
            )
        ComposeOverrideRenderer._append_repository_mounts(lines, repositories)
        lines.extend(
            [
                "      - type: bind",
                f"        source: {yaml_quote(str(aliases))}",
                "        target: /run/devcontainer/allowlist.tsv",
                "        read_only: true",
            ]
        )

    @staticmethod
    def _append_repository_mounts(
        lines: list[str],
        repositories: list[AllowlistedRepository],
    ) -> None:
        for repository in repositories:
            lines.extend(
                [
                    "      - type: bind",
                    f"        source: {yaml_quote(str(repository.source))}",
                    f"        target: {yaml_quote(str(repository.target))}",
                    "        read_only: false",
                ]
            )

    @staticmethod
    def _append_ssh_agent_service(
        lines: list[str],
        repo_root: Path,
        ssh_agent_socket: Path,
    ) -> None:
        lines.extend(
            [
                "  ssh-agent:",
                "    build:",
                f"      context: {yaml_quote(str(repo_root))}",
                "      dockerfile: .devcontainer/ssh-agent.Dockerfile",
                '    entrypoint: ["/usr/bin/socat"]',
                "    command:",
                "      - UNIX-LISTEN:/run/ssh-agent/agent.sock,fork,mode=0666,unlink-early,unlink-close",
                "      - UNIX-CONNECT:/run/host-ssh-agent.sock",
                "    user: root",
                "    working_dir: /",
                "    security_opt:",
                "      - no-new-privileges:true",
                "    cap_drop:",
                "      - ALL",
                "    volumes:",
                "      - type: volume",
                "        source: ssh-agent-socket",
                "        target: /run/ssh-agent",
                "      - type: bind",
                f"        source: {yaml_quote(str(ssh_agent_socket))}",
                "        target: /run/host-ssh-agent.sock",
                "        read_only: true",
                "    healthcheck:",
                '      test: ["CMD-SHELL", "test -S /run/ssh-agent/agent.sock"]',
                "      interval: 1s",
                "      timeout: 1s",
                "      retries: 30",
                "volumes:",
                "  ssh-agent-socket:",
            ]
        )
