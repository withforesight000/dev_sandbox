"""Internal modules for host-side Devcontainer preparation."""

from .allowlist import AllowlistValidator
from .application import (
    PrepareMounts,
    SubprocessCommandRunner,
    build_application,
)
from .cli import main
from .compose import ComposeOverrideRenderer, yaml_quote
from .errors import AllowlistError
from .models import (
    AllowlistedRepository,
    ContainerMountPath,
    DnsServers,
    PreparationPaths,
)
from .ports import CommandRunner, GeneratedFileWriter, ResolverDetector
from .resolver import (
    RESOLVER_COMMAND_TIMEOUT_SECONDS,
    SCUTIL_NAMESERVER_PATTERN,
    SYSTEMD_RESOLV_CONF_PATH,
    HostResolverDetector,
)
from .writer import AtomicGeneratedFileWriter

__all__ = [
    "RESOLVER_COMMAND_TIMEOUT_SECONDS",
    "SCUTIL_NAMESERVER_PATTERN",
    "SYSTEMD_RESOLV_CONF_PATH",
    "AllowlistError",
    "AllowlistValidator",
    "AllowlistedRepository",
    "AtomicGeneratedFileWriter",
    "CommandRunner",
    "ComposeOverrideRenderer",
    "ContainerMountPath",
    "DnsServers",
    "GeneratedFileWriter",
    "HostResolverDetector",
    "PreparationPaths",
    "PrepareMounts",
    "ResolverDetector",
    "SubprocessCommandRunner",
    "build_application",
    "main",
    "yaml_quote",
]
