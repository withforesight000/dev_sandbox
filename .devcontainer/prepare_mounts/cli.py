"""Command-line entry point for host-side Devcontainer preparation."""

from __future__ import annotations

import sys
from pathlib import Path

from .application import build_application
from .errors import AllowlistError
from .models import PreparationPaths


def main(script_path: Path | None = None) -> int:
    """Run the host-side allowlist preparation command."""

    entrypoint = (
        script_path
        if script_path is not None
        else Path(__file__).resolve().parents[1] / "prepare-mounts.py"
    )
    paths = PreparationPaths.from_script(entrypoint)
    try:
        build_application().run(paths)
    except AllowlistError as error:
        print(f"devcontainer allowlist: {error}", file=sys.stderr)
        return 1
    return 0
