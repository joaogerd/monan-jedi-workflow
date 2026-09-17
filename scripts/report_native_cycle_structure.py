#!/usr/bin/env python3
"""Print deterministic structural metrics for native-cycle campaign workflows."""

from __future__ import annotations

import json

import yaml

from monan_jedi_workflow.corrected_campaign import (
    _cycles,
    build_corrected_campaign_workflow,
)

PERIODS = {
    "3d": "2018-04-18T00:00:00Z",
    "7d": "2018-04-22T00:00:00Z",
    "30d": "2018-05-15T00:00:00Z",
    "365d": "2019-04-15T00:00:00Z",
}
START = "2018-04-15T00:00:00Z"


def main() -> int:
    report: dict[str, dict[str, object]] = {}
    task_sets: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    structural_counts: set[int] = set()

    for label, end in PERIODS.items():
        document = build_corrected_campaign_workflow(
            start_cycle=START,
            end_cycle=end,
            experiment_dir="/tmp/campaign",
        )
        initialization = tuple(task["name"] for task in document["initialization"]["tasks"])
        tasks = tuple(task["name"] for task in document["tasks"])
        rendered = yaml.safe_dump(document, sort_keys=False).encode("utf-8")
        task_sets.add((initialization, tasks))
        structural_counts.add(len(initialization) + len(tasks))
        report[label] = {
            "start": START,
            "end": end,
            "cycle_count": len(_cycles(START, end)),
            "initialization_task_definitions": len(initialization),
            "cycle_task_definitions": len(tasks),
            "structural_task_definitions": len(initialization) + len(tasks),
            "workflow_yaml_bytes": len(rendered),
        }

    if len(task_sets) != 1 or len(structural_counts) != 1:
        raise RuntimeError("native-cycle workflow structure grows with campaign duration")

    sizes = [int(item["workflow_yaml_bytes"]) for item in report.values()]
    summary = {
        "periods": report,
        "structural_task_sets_identical": True,
        "workflow_size_spread_bytes": max(sizes) - min(sizes),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
