"""Compose override rendering for the Devcontainer services."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from .models import AllowlistedRepository, DnsServers


def yaml_quote(value: str) -> str:
    """Quote a scalar for the single-quoted YAML values in the override."""

    return "'" + value.replace("'", "''") + "'"


class ComposeOverrideRenderer:
    """Render the generated Compose override without external YAML packages."""

    def render(
        self,
        repositories: list[AllowlistedRepository],
        repo_root: Path,
        ssh_agent_socket: Path | None,
        dns_servers: DnsServers | None = None,
    ) -> str:
        """Render workspace, Docker daemon, and optional SSH relay services."""

        workspace_parents = self._workspace_parent_paths(repositories)
        lines = ["services:", "  workspace:"]
        self._append_workspace_service(
            lines,
            repositories,
            workspace_parents,
            ssh_agent_socket,
        )
        lines.append("  docker:")
        if dns_servers:
            lines.extend(
                [
                    "    environment:",
                    f"      ROOTLESS_DOCKER_DNS: {yaml_quote(dns_servers.as_environment_value())}",
                ]
            )
        ComposeOverrideRenderer._append_tmpfs_mounts(lines, workspace_parents)
        lines.append("    volumes:")
        self._append_repository_mounts(lines, repositories)
        if ssh_agent_socket is not None:
            self._append_ssh_agent_service(lines, repo_root, ssh_agent_socket)
        return "\n".join(lines) + "\n"

    @staticmethod
    def _append_workspace_service(
        lines: list[str],
        repositories: list[AllowlistedRepository],
        workspace_parents: tuple[PurePosixPath, ...],
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
        ComposeOverrideRenderer._append_tmpfs_mounts(lines, workspace_parents)
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

    @staticmethod
    def _workspace_parent_paths(
        repositories: list[AllowlistedRepository],
    ) -> tuple[PurePosixPath, ...]:
        """Return unique synthetic parent paths in mount order."""

        paths = {
            parent
            for repository in repositories
            for parent in repository.target.workspace_parent_paths
        }
        return tuple(sorted(paths, key=lambda path: (len(path.parts), str(path))))

    @staticmethod
    def _append_tmpfs_mounts(
        lines: list[str],
        workspace_parents: tuple[PurePosixPath, ...],
    ) -> None:
        if not workspace_parents:
            return
        lines.append("    tmpfs:")
        for parent in workspace_parents:
            options = f"{parent}:uid=1000,gid=1000,mode=0755"
            lines.append(f"      - {yaml_quote(options)}")

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
