"""Host DNS resolver detection for the nested rootless Docker daemon."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from .models import DnsServers
from .ports import CommandRunner

_REGEX_ESCAPE = chr(92)
SCUTIL_NAMESERVER_PATTERN = re.compile(
    f"^{_REGEX_ESCAPE}s*nameserver{_REGEX_ESCAPE}[{_REGEX_ESCAPE}d+{_REGEX_ESCAPE}]"
    f"{_REGEX_ESCAPE}s*:{_REGEX_ESCAPE}s*({_REGEX_ESCAPE}S+){_REGEX_ESCAPE}s*$"
)


class HostResolverDetector:
    """Detect host DNS servers without depending on the outer Docker namespace."""

    def __init__(
        self,
        command_runner: CommandRunner,
        platform_name: str | None = None,
        resolv_conf_path: Path = Path("/etc/resolv.conf"),
    ) -> None:
        self._command_runner = command_runner
        self._platform_name = (
            platform_name if platform_name is not None else sys.platform
        )
        self._resolv_conf_path = resolv_conf_path

    def detect(self, explicit_override: str | None) -> DnsServers | None:
        """Prefer an explicit override, then use the host's platform resolver APIs."""

        if explicit_override is not None and explicit_override.strip():
            return DnsServers.from_explicit(explicit_override)

        if self._platform_name == "darwin":
            servers = self._detect_with_scutil()
            if servers:
                return servers
            return self._detect_from_resolv_conf()

        if self._platform_name.startswith("linux"):
            servers = self._detect_from_resolv_conf()
            if servers:
                return servers
            return self._detect_with_resolvectl()

        return self._detect_from_resolv_conf()

    def _detect_with_scutil(self) -> DnsServers | None:
        try:
            result = self._command_runner.run(["/usr/sbin/scutil", "--dns"])
        except (OSError, UnicodeError):
            return None
        if result.returncode != 0:
            return None

        values = [
            match.group(1)
            for line in (result.stdout or "").splitlines()
            if (match := SCUTIL_NAMESERVER_PATTERN.match(line))
        ]
        return DnsServers.from_detected(values)

    def _detect_with_resolvectl(self) -> DnsServers | None:
        try:
            result = self._command_runner.run(["resolvectl", "dns"])
        except (OSError, UnicodeError):
            return None
        if result.returncode != 0:
            return None

        values: list[str] = []
        for line in (result.stdout or "").splitlines():
            if "DNS Servers:" not in line:
                continue
            values.extend(line.split("DNS Servers:", 1)[1].split())
        return DnsServers.from_detected(values)

    def _detect_from_resolv_conf(self) -> DnsServers | None:
        try:
            content = self._resolv_conf_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return None

        values: list[str] = []
        for raw_line in content.splitlines():
            line = raw_line.split("#", 1)[0]
            fields = line.split()
            if len(fields) >= 2 and fields[0] == "nameserver":
                values.append(fields[1])
        return DnsServers.from_detected(values)
