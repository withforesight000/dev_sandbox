"""Atomic writing of generated Devcontainer files."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class AtomicGeneratedFileWriter:
    """Write the generated Compose override atomically."""

    def write(
        self,
        override: Path,
        override_content: str,
    ) -> None:
        """Replace the generated Compose override."""

        temporary_path: Path | None = None
        try:
            temporary_path = self._write_temp_file(
                override,
                override_content,
                prefix=".compose.allowlist.",
            )
            os.replace(temporary_path, override)
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass

    @staticmethod
    def _write_temp_file(target: Path, content: str, prefix: str) -> Path:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=prefix,
            dir=target.parent,
            delete=False,
        ) as handle:
            handle.write(content)
            return Path(handle.name)
