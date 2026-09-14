"""Allowlist parsing and mount-path validation."""

from __future__ import annotations

import re
import stat
from pathlib import Path
from typing import TextIO

from .errors import AllowlistError
from .models import AllowlistedRepository, ContainerMountPath
from .ports import CommandRunner


class AllowlistValidator:
    """Parse allowlist rows and enforce the mount security invariants."""

    def __init__(self, command_runner: CommandRunner) -> None:
        self._command_runner = command_runner

    def parse(
        self,
        allowlist: Path,
        repo_root: Path,
    ) -> list[AllowlistedRepository]:
        """Read and validate all allowlist rows from allowlist."""

        if not allowlist.is_file():
            raise AllowlistError(f"missing {allowlist}")

        try:
            with allowlist.open("r", encoding="utf-8", newline="") as handle:
                repositories = self._parse_rows(handle, repo_root)
        except (OSError, UnicodeError) as error:
            raise AllowlistError(f"cannot read {allowlist}: {error}") from error

        return repositories

    def resolve_ssh_agent_socket(self, socket_value: str | None) -> Path | None:
        """Validate and resolve the optional host SSH agent socket."""

        if not socket_value:
            return None
        if "\x00" in socket_value:
            raise AllowlistError("SSH_AUTH_SOCK is not a valid path")

        try:
            socket_path = Path(socket_value)
        except (TypeError, ValueError) as error:
            raise AllowlistError("SSH_AUTH_SOCK is not a valid path") from error
        if not socket_path.is_absolute():
            raise AllowlistError("SSH_AUTH_SOCK must be an absolute path")
        if not self._is_unix_socket(socket_path):
            raise AllowlistError(f"SSH_AUTH_SOCK is not a Unix socket: {socket_path}")

        resolved = self._resolve_existing_path(socket_path)
        if resolved is None:
            raise AllowlistError(f"cannot resolve SSH_AUTH_SOCK: {socket_path}")
        if not self._is_unix_socket(resolved):
            raise AllowlistError(
                f"resolved SSH_AUTH_SOCK is not a Unix socket: {resolved}"
            )
        return resolved

    def _parse_rows(
        self,
        handle: TextIO,
        repo_root: Path,
    ) -> list[AllowlistedRepository]:
        repositories: list[AllowlistedRepository] = []
        for raw_line in handle:
            line = raw_line.removesuffix("\n")
            if not line.strip() or line.startswith("#"):
                continue

            fields = re.split(r"\t+", line)
            if len(fields) != 2:
                raise AllowlistError(
                    "allowlist rows must contain exactly two tab-separated fields"
                )
            source_spec, target = fields
            if not source_spec:
                raise AllowlistError("missing host path")

            repository = AllowlistedRepository(
                source=self._resolve_source(source_spec, repo_root),
                target=ContainerMountPath.parse(target),
            )
            self._validate_repository(repository, repo_root)
            self._validate_relationships(repository, repositories)
            repositories.append(repository)
        return repositories

    def _resolve_source(
        self,
        source_spec: str,
        repo_root: Path,
    ) -> Path:
        if "\n" in source_spec or "\r" in source_spec or "\x00" in source_spec:
            raise AllowlistError("invalid control character in host path")

        if source_spec == "@workspace":
            source_path = repo_root
        elif source_spec.startswith("@workspace:"):
            absolute_source = source_spec[len("@workspace:") :]
            if not absolute_source or not Path(absolute_source).is_absolute():
                raise AllowlistError(
                    "workspace absolute path must be non-empty and absolute"
                )
            source_path = Path(absolute_source)
        elif source_spec.startswith("@workspace-relative:"):
            relative_source = source_spec[len("@workspace-relative:") :]
            if not relative_source or Path(relative_source).is_absolute():
                raise AllowlistError(
                    "workspace-relative path must be non-empty and relative"
                )
            source_path = repo_root / relative_source
        else:
            source_path = Path(source_spec)

        if not source_path.is_absolute():
            raise AllowlistError("host path must be absolute")
        resolved = self._resolve_existing_path(source_path)
        if resolved is None:
            raise AllowlistError(f"host path does not exist: {source_path}")
        if not resolved.is_dir():
            raise AllowlistError(f"host path is not a directory: {resolved}")
        return resolved

    @staticmethod
    def _resolve_existing_path(path: Path) -> Path | None:
        try:
            return path.resolve(strict=True)
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            return None

    def _validate_repository(
        self,
        repository: AllowlistedRepository,
        repo_root: Path,
    ) -> None:
        if repository.source == repo_root:
            return

        git_root = self._git_repository_root(repository.source)
        if git_root is None:
            raise AllowlistError(
                f"allowlisted path is not a Git repository: {repository.source}"
            )
        if git_root != repository.source:
            raise AllowlistError(
                f"allowlist entries must be repository roots: {repository.source}"
            )

    def _git_repository_root(self, path: Path) -> Path | None:
        try:
            result = self._command_runner.run(
                ["git", "-C", str(path), "rev-parse", "--show-toplevel"]
            )
        except (OSError, UnicodeError):
            return None
        if result.returncode != 0:
            return None

        git_root_text = (result.stdout or "").rstrip("\r\n")
        if not git_root_text:
            return None
        return self._resolve_existing_path(Path(git_root_text))

    @staticmethod
    def _validate_relationships(
        repository: AllowlistedRepository,
        existing_repositories: list[AllowlistedRepository],
    ) -> None:
        """Reject duplicate and nested host or container mount paths."""

        for existing in existing_repositories:
            if existing.has_same_source_as(repository):
                raise AllowlistError(f"duplicate repository path: {repository.source}")
            if existing.has_same_target_as(repository):
                raise AllowlistError(
                    f"duplicate container mount path: {repository.target}"
                )
            if repository.is_source_nested_under(existing):
                raise AllowlistError(
                    f"nested allowlist paths are not allowed: {repository.source}"
                )
            if existing.is_source_nested_under(repository):
                raise AllowlistError(
                    f"nested allowlist paths are not allowed: {existing.source}"
                )
            if repository.is_target_nested_under(existing):
                raise AllowlistError(
                    f"nested container mount paths are not allowed: {repository.target}"
                )
            if existing.is_target_nested_under(repository):
                raise AllowlistError(
                    f"nested container mount paths are not allowed: {existing.target}"
                )

    @staticmethod
    def _is_unix_socket(path: Path) -> bool:
        try:
            return stat.S_ISSOCK(path.stat().st_mode)
        except OSError:
            return False
