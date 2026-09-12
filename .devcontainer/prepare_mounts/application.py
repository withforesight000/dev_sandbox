"""Application orchestration for host-side Devcontainer preparation."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from typing import TextIO

from .allowlist import AllowlistValidator
from .compose import ComposeOverrideRenderer
from .errors import AllowlistError
from .models import DnsServers, PreparationPaths
from .ports import GeneratedFileWriter, ResolverDetector
from .resolver import HostResolverDetector
from .writer import AtomicGeneratedFileWriter


class SubprocessCommandRunner:
    """Production command runner used for host command detection."""

    def run(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        """Run command while allowing the validator to handle its exit code."""

        return subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            encoding="utf-8",
        )


class PrepareMounts:
    """Application service coordinating validation, rendering, and output."""

    def __init__(
        self,
        validator: AllowlistValidator,
        renderer: ComposeOverrideRenderer,
        writer: GeneratedFileWriter,
        resolver_detector: ResolverDetector | None = None,
        environment: Mapping[str, str] | None = None,
        output: TextIO | None = None,
    ) -> None:
        self._validator = validator
        self._renderer = renderer
        self._writer = writer
        self._resolver_detector = resolver_detector
        self._environment = environment if environment is not None else os.environ
        self._output = output if output is not None else sys.stdout

    def run(self, paths: PreparationPaths) -> None:
        """Prepare generated files for the supplied repository paths."""

        repositories = self._validator.parse(paths.allowlist, paths.repo_root)
        ssh_agent_socket = self._validator.resolve_ssh_agent_socket(
            self._environment.get("SSH_AUTH_SOCK")
        )
        dns_servers: DnsServers | None = None
        if self._resolver_detector is not None:
            dns_servers = self._resolver_detector.detect(
                self._environment.get("ROOTLESS_DOCKER_DNS")
            )
        aliases_content = "".join(
            f"{repository.workspace_alias}\t{repository.target}\n"
            for repository in repositories
        )
        override_content = self._renderer.render(
            repositories,
            paths.aliases,
            paths.repo_root,
            ssh_agent_socket,
            dns_servers,
        )
        try:
            self._writer.write(
                paths.override,
                paths.aliases,
                override_content,
                aliases_content,
            )
        except OSError as error:
            raise AllowlistError(
                f"cannot generate local Compose files: {error}"
            ) from error

        print(
            f"devcontainer allowlist: validated {len(repositories)} repository/repositories",
            file=self._output,
        )
        print(
            f"devcontainer allowlist: generated {paths.override}",
            file=self._output,
        )
        if dns_servers is not None:
            print(
                f"devcontainer DNS: detected {len(dns_servers)} usable resolver(s)",
                file=self._output,
            )
        else:
            print(
                "devcontainer DNS: no usable host resolver detected; rootless Docker startup will fail",
                file=self._output,
            )
        if ssh_agent_socket is not None:
            print(
                "devcontainer ssh agent: enabled for workspace via relay",
                file=self._output,
            )


def build_application() -> PrepareMounts:
    """Build the production application with concrete dependencies."""

    return PrepareMounts(
        validator=AllowlistValidator(SubprocessCommandRunner()),
        renderer=ComposeOverrideRenderer(),
        writer=AtomicGeneratedFileWriter(),
        resolver_detector=HostResolverDetector(SubprocessCommandRunner()),
    )
