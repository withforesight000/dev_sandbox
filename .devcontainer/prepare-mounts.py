#!/usr/bin/env python3
"""Compatibility entry point for host-side Devcontainer preparation."""

from pathlib import Path

from prepare_mounts.cli import main

if __name__ == "__main__":
    raise SystemExit(main(Path(__file__)))
