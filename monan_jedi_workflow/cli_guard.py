"""CLI guard helpers."""

from __future__ import annotations


def format_error(message: str) -> str:
    return f"MONAN-JEDI workflow stopped\n{message}"
