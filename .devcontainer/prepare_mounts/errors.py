"""Exceptions raised while preparing the Devcontainer configuration."""

from __future__ import annotations


class AllowlistError(Exception):
    """An expected validation or local file generation error."""
