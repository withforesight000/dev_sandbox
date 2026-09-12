"""Value object for normalized container mount paths."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import PurePosixPath

from ..errors import AllowlistError


@dataclass(frozen=True)
class ContainerMountPath:
    """An absolute, normalized, non-reserved container mount path."""

    value: str

    def __post_init__(self) -> None:
        self._validate(self.value)

    @classmethod
    def parse(cls, value: str) -> ContainerMountPath:
        """Validate a raw allowlist value and return its domain representation."""

        cls._validate(value)
        return cls(value)

    @property
    def basename(self) -> str:
        """Return the final path component used for the workspace alias."""

        return PurePosixPath(self.value).name

    def is_nested_under(self, other: ContainerMountPath) -> bool:
        """Return whether this mount path is nested under another path."""

        candidate = PurePosixPath(self.value)
        existing = PurePosixPath(other.value)
        return candidate != existing and existing in candidate.parents

    def __str__(self) -> str:
        return self.value

    @staticmethod
    def _validate(value: str) -> None:
        if not isinstance(value, str) or not value:
            raise AllowlistError("missing container mount path")
        if not value.startswith("/"):
            raise AllowlistError("container mount path must be absolute")
        if value == "/":
            raise AllowlistError("container mount path must not be the filesystem root")
        if value == "/workspaces":
            raise AllowlistError(
                "container mount path is reserved for workspace aliases: /workspaces"
            )
        if value.endswith("/"):
            raise AllowlistError("container mount path must not have a trailing slash")
        if "\n" in value or "\r" in value or "\x00" in value:
            raise AllowlistError("invalid control character in container mount path")
        if "//" in value or posixpath.normpath(value) != value:
            raise AllowlistError(f"container mount path must be normalized: {value}")
