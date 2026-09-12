"""Protocols for external commands, resolver detection, and file output."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .models.dns import DnsServers


class CommandRunner(Protocol):
    """Run an external command and return its completed process result."""

    def run(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        """Run command without raising for a non-zero exit code."""
        ...


class ResolverDetector(Protocol):
    """Resolve usable host DNS servers for the nested Docker daemon."""

    def detect(self, explicit_override: str | None) -> DnsServers | None:
        """Return ordered DNS server addresses or None when none are found."""
        ...


class GeneratedFileWriter(Protocol):
    """Write the generated Compose and alias files."""

    def write(
        self,
        override: Path,
        aliases: Path,
        override_content: str,
        aliases_content: str,
    ) -> None:
        """Write both generated files atomically."""
        ...
