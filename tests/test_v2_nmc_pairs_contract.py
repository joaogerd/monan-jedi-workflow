"""Tests for the V2 NMC pair contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from monan_jedi_workflow.components.bmatrix.nmc_pairs import (
    BflowManifest,
    BflowManifestEntry,
    NmcForecast,
    NmcPairError,
    plan_pairs,
    read_bflow_manifest,
    validate_pairs,
    write_bflow_manifest,
)


def _resolver(root: Path):
    """Build a deterministic MPAS product resolver for NMC tests."""

    def resolve(init_time: str, lead_hours: int) -> NmcForecast:
        """Return expected restart and MPAS state paths for one forecast."""
        label = init_time.replace(":", ".") + f".f{lead_hours:03d}"
        return NmcForecast(
            init_time=init_time,
            lead_hours=lead_hours,
            restart=root / f"restart.{label}.nc",
            state=root / f"mpasout.{label}.nc",
        )

    return resolve


def test_plan_pairs_enforces_f048_f024_common_valid_time(tmp_path: Path) -> None:
    """The pair planner must produce the expected old/new initialization times."""
    pairs = plan_pairs(
        [
            "2026-06-22T00:00:00Z",
            "2026-06-23T00:00:00Z",
            "2026-06-24T00:00:00Z",
            "2026-06-25T00:00:00Z",
        ],
        older_lead_hours=48,
        newer_lead_hours=24,
        resolve_forecast=_resolver(tmp_path),
    )

    assert len(pairs) == 4
    assert pairs[0].valid_time == "2026-06-22_00:00:00"
    assert pairs[0].older.init_time == "2026-06-20_00:00:00"
    assert pairs[0].newer.init_time == "2026-06-21_00:00:00"
    assert validate_pairs(pairs, require_products=False).is_valid


def test_plan_pairs_rejects_invalid_lead_order(tmp_path: Path) -> None:
    """The older member must have the strictly longer forecast lead."""
    with pytest.raises(NmcPairError, match="older_lead_hours"):
        plan_pairs(
            ["2026-06-22T00:00:00Z"],
            older_lead_hours=24,
            newer_lead_hours=48,
            resolve_forecast=_resolver(tmp_path),
        )


def test_bflow_manifest_round_trip_preserves_contract(tmp_path: Path) -> None:
    """The TSV hand-off format must retain normalized times and absolute paths."""
    entries = []
    for day in range(22, 26):
        f048 = tmp_path / f"f048_{day}.nc"
        f024 = tmp_path / f"f024_{day}.nc"
        f048.write_bytes(b"old")
        f024.write_bytes(b"new")
        entries.append(BflowManifestEntry(f"2026-06-{day}T00:00:00Z", f048, f024))

    path = write_bflow_manifest(tmp_path / "bflow-manifest.tsv", BflowManifest(tuple(entries)))
    parsed = read_bflow_manifest(path)

    assert parsed == BflowManifest(tuple(entries))
    assert path.read_text(encoding="utf-8").splitlines()[0] == "valid_time\tf048\tf024"
