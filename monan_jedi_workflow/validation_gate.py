"""Generic validation-manifest gate for external orchestrators.

The domain stages remain responsible for producing their scientific validation
manifests.  This module only enforces the small orchestration contract used by
simpleWorkflow/ecFlow/Cylc adapters: a downstream stage may proceed only when
the declared upstream validation manifest exists, is valid JSON, and contains
``valid: true``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ValidationGateError(RuntimeError):
    """A stage validation manifest cannot authorize downstream execution."""


def require_valid_manifest(path: str | Path) -> dict[str, Any]:
    """Read *path* and require the canonical ``valid: true`` contract."""
    manifest = Path(path)
    if not manifest.is_file():
        raise ValidationGateError(f"validation manifest does not exist: {manifest}")

    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationGateError(
            f"cannot read validation manifest {manifest}: {error}"
        ) from error

    if not isinstance(payload, dict):
        raise ValidationGateError(
            f"validation manifest must contain a JSON object: {manifest}"
        )
    if payload.get("valid") is not True:
        raise ValidationGateError(
            f"validation manifest is not valid=true: {manifest}"
        )
    return payload
