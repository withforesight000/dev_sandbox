"""Value object for paths used by host-side Devcontainer preparation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreparationPaths:
    """Paths used by the host-side allowlist preparation use case."""

    repo_root: Path
    allowlist: Path
    override: Path

    @classmethod
    def from_script(cls, script_path: Path) -> PreparationPaths:
        """Build repository-relative paths from the running script path."""

        script_dir = script_path.resolve().parent
        return cls(
            repo_root=script_dir.parent,
            allowlist=script_dir / "allowlist.tsv",
            override=script_dir / "compose.allowlist.local.yml",
        )
