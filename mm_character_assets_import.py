"""Test-only import bridge for the hyphenated skill directory."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "mm-character-assets" / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_spec = _load("validate_spec")
plan_board = _load("plan_board")
compose_board = _load("compose_board")
