"""Domain model for an allowlisted repository mount."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .mount import ContainerMountPath


@dataclass(frozen=True)
class AllowlistedRepository:
    """A validated host repository and its container mount destination."""

    source: Path
    target: ContainerMountPath

    @property
    def workspace_alias(self) -> str:
        """Return the navigation alias derived from the mount destination."""

        return self.target.basename

    @property
    def workspace_alias_path(self) -> PurePosixPath:
        """Return the absolute container path used for the navigation alias."""

        return PurePosixPath("/workspaces") / self.workspace_alias

    def __post_init__(self) -> None:
        if not isinstance(self.target, ContainerMountPath):
            object.__setattr__(self, "target", ContainerMountPath(self.target))

    def has_same_source_as(self, other: AllowlistedRepository) -> bool:
        """Return whether both repositories refer to the same host path."""

        return self.source == other.source

    def has_same_target_as(self, other: AllowlistedRepository) -> bool:
        """Return whether both repositories use the same container path."""

        return self.target == other.target

    def is_source_nested_under(self, other: AllowlistedRepository) -> bool:
        """Return whether this repository's host path is nested under another."""

        return _is_nested_path(self.source, other.source)

    def is_target_nested_under(self, other: AllowlistedRepository) -> bool:
        """Return whether this repository's container path is nested under another."""

        return self.target.is_nested_under(other.target)


def _is_nested_path(candidate: Path, existing: Path) -> bool:
    return candidate != existing and existing in candidate.parents
