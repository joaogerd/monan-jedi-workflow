"""Compare scientific contents of two NetCDF files.

The comparator is intended for reproducibility checks between MONAN/MPAS-JEDI
runs.  It compares dimensions, variable inventories, dtypes, attributes and
stored variable values while allowing volatile global attributes such as
``file_id`` to be ignored explicitly.

Data are read in bounded chunks so large MPAS files do not need to fit in
memory at once.  Exit status 0 means equivalent under the selected tolerances;
exit status 1 means differences were found.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from netCDF4 import Dataset


_DEFAULT_IGNORED_GLOBAL_ATTRS = ("file_id",)
_DEFAULT_CHUNK_BYTES = 64 * 1024 * 1024


@dataclass
class CompareReport:
    """Structured result of one NetCDF comparison."""

    reference: Path
    candidate: Path
    variables_compared: int = 0
    variables_identical: int = 0
    differences: list[str] = field(default_factory=list)
    data_differences: list[str] = field(default_factory=list)

    @property
    def equivalent(self) -> bool:
        return not self.differences and not self.data_differences


def _attribute_equal(left: Any, right: Any) -> bool:
    """Compare NetCDF attributes without lossy string conversion."""
    try:
        return bool(np.array_equal(np.asarray(left), np.asarray(right), equal_nan=True))
    except TypeError:
        return bool(np.array_equal(np.asarray(left), np.asarray(right)))


def _iter_slices(shape: tuple[int, ...], dtype: np.dtype, chunk_bytes: int) -> Iterable[Any]:
    """Yield slices whose approximate raw payload stays below ``chunk_bytes``."""
    if not shape:
        yield (...,)
        return
    trailing = int(np.prod(shape[1:], dtype=np.int64)) if len(shape) > 1 else 1
    itemsize = max(1, int(getattr(dtype, "itemsize", 1) or 1))
    rows = max(1, chunk_bytes // max(1, trailing * itemsize))
    for start in range(0, shape[0], rows):
        yield (slice(start, min(shape[0], start + rows)),) + (slice(None),) * (len(shape) - 1)


def _numeric_chunk_equal(a: np.ndarray, b: np.ndarray, rtol: float, atol: float) -> np.ndarray:
    if rtol == 0.0 and atol == 0.0:
        equal = np.equal(a, b)
        if np.issubdtype(a.dtype, np.floating) or np.issubdtype(a.dtype, np.complexfloating):
            equal = equal | (np.isnan(a) & np.isnan(b))
        return equal
    return np.isclose(a, b, rtol=rtol, atol=atol, equal_nan=True)


def _compare_variable_data(
    name: str,
    ref_var: Any,
    new_var: Any,
    *,
    rtol: float,
    atol: float,
    chunk_bytes: int,
) -> str | None:
    """Return a concise difference summary, or ``None`` when data match."""
    shape = tuple(ref_var.shape)
    dtype = np.dtype(ref_var.dtype)
    numeric = np.issubdtype(dtype, np.number)
    total_neq = 0
    finite_count = 0
    finite_abs_sum = 0.0
    finite_abs_max = 0.0

    for selector in _iter_slices(shape, dtype, chunk_bytes):
        a = np.asarray(ref_var[selector])
        b = np.asarray(new_var[selector])

        if numeric:
            equal = _numeric_chunk_equal(a, b, rtol, atol)
        else:
            equal = np.equal(a, b)

        neq = int(equal.size - np.count_nonzero(equal))
        if neq == 0:
            continue
        total_neq += neq

        if numeric:
            finite = np.isfinite(a) & np.isfinite(b) & ~equal
            if np.any(finite):
                diff = np.abs(a[finite].astype(np.complex128 if np.iscomplexobj(a) else np.float64) - b[finite].astype(np.complex128 if np.iscomplexobj(b) else np.float64))
                diff = np.asarray(diff, dtype=np.float64)
                finite_count += int(diff.size)
                finite_abs_sum += float(diff.sum(dtype=np.float64))
                finite_abs_max = max(finite_abs_max, float(diff.max()))

    if total_neq == 0:
        return None
    if numeric and finite_count:
        return (
            f"{name}: data differ; neq={total_neq}, "
            f"max_abs={finite_abs_max:.17g}, "
            f"mean_abs={finite_abs_sum / finite_count:.17g}"
        )
    return f"{name}: data differ; neq={total_neq}"


def compare_netcdf(
    reference: str | Path,
    candidate: str | Path,
    *,
    ignore_global_attrs: Iterable[str] = _DEFAULT_IGNORED_GLOBAL_ATTRS,
    rtol: float = 0.0,
    atol: float = 0.0,
    chunk_bytes: int = _DEFAULT_CHUNK_BYTES,
) -> CompareReport:
    """Compare two NetCDF files and return a structured report.

    Parameters
    ----------
    reference, candidate
        NetCDF files to compare.
    ignore_global_attrs
        Global attributes excluded from comparison. ``file_id`` is ignored by
        default because MPAS writes a fresh identifier for each output file.
    rtol, atol
        Relative and absolute numeric tolerances. Both default to zero, giving
        exact stored-value comparison (with NaNs considered equal).
    chunk_bytes
        Approximate maximum payload read from each variable per comparison
        block.
    """
    reference = Path(reference)
    candidate = Path(candidate)
    report = CompareReport(reference=reference, candidate=candidate)
    ignored = set(ignore_global_attrs)

    with Dataset(reference) as ref, Dataset(candidate) as new:
        for ds in (ref, new):
            ds.set_auto_mask(False)
            ds.set_auto_scale(False)

        ref_dims = set(ref.dimensions)
        new_dims = set(new.dimensions)
        if ref_dims != new_dims:
            report.differences.append(
                f"dimension inventory differs: only reference={sorted(ref_dims-new_dims)}, "
                f"only candidate={sorted(new_dims-ref_dims)}"
            )
        for name in sorted(ref_dims & new_dims):
            left = len(ref.dimensions[name])
            right = len(new.dimensions[name])
            if left != right:
                report.differences.append(f"dimension {name}: {left} != {right}")

        attrs = (set(ref.ncattrs()) | set(new.ncattrs())) - ignored
        for name in sorted(attrs):
            if name not in ref.ncattrs():
                report.differences.append(f"global attribute {name}: missing from reference")
                continue
            if name not in new.ncattrs():
                report.differences.append(f"global attribute {name}: missing from candidate")
                continue
            if not _attribute_equal(ref.getncattr(name), new.getncattr(name)):
                report.differences.append(
                    f"global attribute {name}: {ref.getncattr(name)!r} != {new.getncattr(name)!r}"
                )

        ref_vars = set(ref.variables)
        new_vars = set(new.variables)
        if ref_vars != new_vars:
            report.differences.append(
                f"variable inventory differs: only reference={sorted(ref_vars-new_vars)}, "
                f"only candidate={sorted(new_vars-ref_vars)}"
            )

        for name in sorted(ref_vars & new_vars):
            report.variables_compared += 1
            left = ref.variables[name]
            right = new.variables[name]
            variable_ok = True

            if left.dimensions != right.dimensions:
                report.differences.append(
                    f"{name}: dimensions {left.dimensions} != {right.dimensions}"
                )
                continue
            if np.dtype(left.dtype) != np.dtype(right.dtype):
                report.differences.append(f"{name}: dtype {left.dtype} != {right.dtype}")
                continue

            var_attrs = set(left.ncattrs()) | set(right.ncattrs())
            for attr in sorted(var_attrs):
                if attr not in left.ncattrs():
                    report.differences.append(f"{name}: attribute {attr} missing from reference")
                    variable_ok = False
                    continue
                if attr not in right.ncattrs():
                    report.differences.append(f"{name}: attribute {attr} missing from candidate")
                    variable_ok = False
                    continue
                if not _attribute_equal(left.getncattr(attr), right.getncattr(attr)):
                    report.differences.append(
                        f"{name}: attribute {attr}: {left.getncattr(attr)!r} != {right.getncattr(attr)!r}"
                    )
                    variable_ok = False

            data_difference = _compare_variable_data(
                name,
                left,
                right,
                rtol=rtol,
                atol=atol,
                chunk_bytes=chunk_bytes,
            )
            if data_difference is not None:
                report.data_differences.append(data_difference)
                variable_ok = False

            if variable_ok:
                report.variables_identical += 1

    return report


def print_report(report: CompareReport, *, ignored_attrs: Iterable[str], rtol: float, atol: float) -> None:
    """Print a compact human-oriented comparison report."""
    print(f"Reference : {report.reference}")
    print(f"Candidate : {report.candidate}")
    print(f"Variables compared : {report.variables_compared}")
    print(f"Variables equivalent: {report.variables_identical}")
    print(f"Ignored global attrs: {', '.join(sorted(set(ignored_attrs))) or '(none)'}")
    print(f"Numeric tolerance   : rtol={rtol:g}, atol={atol:g}")

    if report.equivalent:
        print("\n[OK] NetCDF scientific contents are equivalent.")
        return

    print("\n[DIFF] NetCDF differences found:")
    for item in report.differences:
        print(f"  - {item}")
    for item in report.data_differences:
        print(f"  - {item}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="monan-jedi-workflow compare-netcdf",
        description="Compare NetCDF structure, metadata and stored variable values.",
    )
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument(
        "--ignore-global-attr",
        action="append",
        default=[],
        metavar="NAME",
        help="Ignore an additional global attribute (repeatable). file_id is ignored by default.",
    )
    parser.add_argument("--compare-file-id", action="store_true", help="Do not ignore the MPAS file_id global attribute.")
    parser.add_argument("--rtol", type=float, default=0.0, help="Relative tolerance for numeric values (default: exact).")
    parser.add_argument("--atol", type=float, default=0.0, help="Absolute tolerance for numeric values (default: exact).")
    parser.add_argument("--chunk-mib", type=float, default=64.0, help="Approximate per-variable read chunk in MiB (default: 64).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.rtol < 0 or args.atol < 0:
        raise SystemExit("--rtol and --atol must be non-negative")
    if args.chunk_mib <= 0:
        raise SystemExit("--chunk-mib must be positive")

    ignored = set(args.ignore_global_attr)
    if not args.compare_file_id:
        ignored.add("file_id")

    report = compare_netcdf(
        args.reference,
        args.candidate,
        ignore_global_attrs=ignored,
        rtol=args.rtol,
        atol=args.atol,
        chunk_bytes=max(1, int(args.chunk_mib * 1024 * 1024)),
    )
    print_report(report, ignored_attrs=ignored, rtol=args.rtol, atol=args.atol)
    return 0 if report.equivalent else 1


if __name__ == "__main__":
    raise SystemExit(main())
