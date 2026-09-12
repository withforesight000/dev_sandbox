"""Atomic writing of generated Devcontainer files."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class AtomicGeneratedFileWriter:
    """Write generated files via temporary files and atomic replacement."""

    def write(
        self,
        override: Path,
        aliases: Path,
        override_content: str,
        aliases_content: str,
    ) -> None:
        """Replace both generated files while cleaning up temporary files."""

        temporary_paths: list[Path] = []
        try:
            temporary_override = self._write_temp_file(
                override,
                override_content,
                prefix=".compose.allowlist.",
            )
            temporary_paths.append(temporary_override)
            temporary_aliases = self._write_temp_file(
                aliases,
                aliases_content,
                prefix=".allowlist.",
            )
            temporary_paths.append(temporary_aliases)
            os.chmod(temporary_aliases, 0o644)

            os.replace(temporary_override, override)
            os.replace(temporary_aliases, aliases)
            temporary_paths.clear()
        finally:
            for temporary_path in temporary_paths:
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
