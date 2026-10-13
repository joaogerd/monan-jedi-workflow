"""Compatibility checks for initialized fields and separately read invariants."""
from pathlib import Path

FIELDS = ('zgrid','zz','dzu','rdzu','rdzw','fzm','fzp','zxu','zb','zb3','cf1','cf2','cf3')


def compare_vertical_geometry(state: Path, reference: Path, *, fields=FIELDS) -> list[str]:
    """Reject missing, invalid or incompatible vertical coordinates and metrics."""
    import numpy as np
    from netCDF4 import Dataset

    issues = []
    with Dataset(state) as initial, Dataset(reference) as invariant:
        for name in fields:
            if name not in initial.variables or name not in invariant.variables:
                issues.append(f'geometry field {name} missing in state or reference {reference}')
                continue
            arrays = []
            for dataset in (initial, invariant):
                variable = dataset.variables[name]
                selection = tuple(0 if dim == 'Time' else slice(None) for dim in variable.dimensions)
                arrays.append(np.ma.asarray(variable[selection], dtype=np.float64).filled(np.nan))
            left, right = arrays
            if left.shape != right.shape:
                issues.append(f'geometry {name} shape mismatch: {left.shape} versus {right.shape}')
            elif not (np.isfinite(left).all() and np.isfinite(right).all()):
                issues.append(f'geometry {name} contains masked or nonfinite values')
            elif not np.allclose(left, right, rtol=1e-7, atol=1e-8):
                issues.append(f'geometry {name} differs from {reference}: max_abs_difference={np.max(np.abs(left-right)):.12g}')
    return issues
