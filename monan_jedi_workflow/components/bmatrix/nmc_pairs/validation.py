"""Validation routines for NMC forecast pairs and BFLOW hand-off files."""

from __future__ import annotations

from .manifest import BflowManifest
from .model import NmcPair
from ....core.validation import ValidationReport


MINIMUM_BMATRIX_PAIRS = 4


def validate_pairs(
    pairs: tuple[NmcPair, ...],
    *,
    minimum_pairs: int = MINIMUM_BMATRIX_PAIRS,
    require_products: bool = True,
) -> ValidationReport:
    """Validate NMC pair geometry and expected MPAS products.

    Parameters
    ----------
    pairs : tuple[NmcPair, ...]
        Planned NMC pairs to validate.
    minimum_pairs : int, default=4
        Minimum number of complete pairs required for B-matrix calibration.
    require_products : bool, default=True
        Require non-empty restart and state products for both members of every
        pair. Set to ``False`` only for planning before MPAS execution.

    Returns
    -------
    ValidationReport
        Report containing all observed failures instead of failing at the first
        missing product.
    """
    report = ValidationReport(subject="nmc_pairs")
    if minimum_pairs < MINIMUM_BMATRIX_PAIRS:
        report.add(
            "nmc.minimum_pairs",
            f"minimum_pairs must be at least {MINIMUM_BMATRIX_PAIRS} for B-matrix calibration.",
        )
    if len(pairs) < minimum_pairs:
        report.add(
            "nmc.pair_count",
            f"NMC pair count {len(pairs)} is below required minimum {minimum_pairs}.",
        )

    times = [pair.valid_time for pair in pairs]
    if times != sorted(times):
        report.add("nmc.order", "NMC pairs must be ordered by valid_time.")
    if len(set(times)) != len(times):
        report.add("nmc.duplicate_time", "NMC pairs must have unique valid times.")

    if not require_products:
        return report

    for pair in pairs:
        for member_name, member in (("f048", pair.older), ("f024", pair.newer)):
            for product_name, path in (("restart", member.restart), ("state", member.state)):
                if not path.is_file() or path.stat().st_size == 0:
                    report.add(
                        "nmc.product_missing",
                        f"Missing or empty {member_name} {product_name} for {pair.valid_time}: {path}",
                        path=str(path),
                    )
    return report


def validate_bflow_manifest(
    manifest: BflowManifest,
    *,
    minimum_pairs: int = MINIMUM_BMATRIX_PAIRS,
    require_files: bool = True,
) -> ValidationReport:
    """Validate a BFLOW hand-off manifest and its state-file products.

    Parameters
    ----------
    manifest : BflowManifest
        Parsed hand-off manifest.
    minimum_pairs : int, default=4
        Minimum number of complete forecast pairs required.
    require_files : bool, default=True
        Require non-empty f048 and f024 files.

    Returns
    -------
    ValidationReport
        Report covering row count, time uniqueness, ordering, and input files.
    """
    report = ValidationReport(subject="bflow_manifest")
    if minimum_pairs < MINIMUM_BMATRIX_PAIRS:
        report.add(
            "nmc.minimum_pairs",
            f"minimum_pairs must be at least {MINIMUM_BMATRIX_PAIRS} for B-matrix calibration.",
        )
    entries = manifest.entries
    if len(entries) < minimum_pairs:
        report.add(
            "nmc.pair_count",
            f"BFLOW manifest contains {len(entries)} pair(s), below required minimum {minimum_pairs}.",
        )
    if not require_files:
        return report

    for entry in entries:
        for name, path in (("f048", entry.f048), ("f024", entry.f024)):
            if not path.is_file() or path.stat().st_size == 0:
                report.add(
                    "bflow.input_missing",
                    f"Missing or empty {name} state file for {entry.valid_time}: {path}",
                    path=str(path),
                )
    return report
