from __future__ import annotations

import pytest

from monan_jedi_workflow.references import (
    CircularReferenceError,
    UnknownReferenceError,
    resolve_references,
)


def test_resolves_nested_references_and_preserves_types() -> None:
    configuration = {
        "installation": {
            "root": "/opt/monan-jedi",
            "bin_root": "{installation.root}/bin",
        },
        "run": {
            "tasks": 128,
            "task_copy": "{run.tasks}",
            "partition": "graph.info.part.{tasks}",
        },
    }

    resolved = resolve_references(configuration)

    assert resolved["installation"]["bin_root"] == "/opt/monan-jedi/bin"
    assert resolved["run"]["task_copy"] == 128
    assert resolved["run"]["partition"] == "graph.info.part.128"


def test_preserves_cycle_placeholders_for_later_resolution() -> None:
    resolved = resolve_references(
        {"site": {"root": "/work"}, "path": "{site.root}/cycles/{cycle_id}"}
    )

    assert resolved["path"] == "/work/cycles/{cycle_id}"


def test_rejects_unknown_reference() -> None:
    with pytest.raises(UnknownReferenceError):
        resolve_references({"value": "{missing}"})


def test_rejects_circular_reference() -> None:
    with pytest.raises(CircularReferenceError):
        resolve_references({"first": "{second}", "second": "{first}"})
