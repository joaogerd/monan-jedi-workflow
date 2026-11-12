"""Paired O-B/O-A diagnostic for the captured September 2025 IODA contract.

This diagnostic measures fit to assimilated observations, not forecast skill.
Run explicitly with ``python -m monan_jedi_workflow.scientific_feedback FILE``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from netCDF4 import Dataset


def paired_feedback(path: str | Path, variable: str) -> dict:
    with Dataset(path) as ds:
        groups = ['ObsValue', 'hofx0', 'hofx1']
        arrays = []
        units = []
        dimensions = []
        for group in groups:
            if group not in ds.groups or variable not in ds[group].variables:
                raise ValueError(f'Missing {group}/{variable}')
            var = ds[group][variable]
            arrays.append(np.ma.asarray(var[:], dtype=np.float64))
            units.append(getattr(var, 'units', None))
            dimensions.append(var.dimensions)
        if not units[0] or len(set(units)) != 1:
            raise ValueError(f'Missing or inconsistent units: {units}')
        shape = arrays[0].shape
        if any(a.shape != shape for a in arrays) or any(d != dimensions[0] for d in dimensions):
            raise ValueError('Feedback dimensions/shapes differ')
        qcs = [name for name in ['EffectiveQC0', 'EffectiveQC1'] if name in ds.groups]
        if not qcs and 'EffectiveQC' in ds.groups:
            qcs = ['EffectiveQC']
        if not qcs:
            raise ValueError('Missing EffectiveQC groups')
        valid = np.ones(shape, dtype=bool)
        for array in arrays:
            values = array.filled(np.nan)
            valid &= ~np.ma.getmaskarray(array) & np.isfinite(values) & (np.abs(values) < 1e30)
        for name in qcs:
            if variable not in ds[name].variables:
                raise ValueError(f'Missing QC variable {name}/{variable}')
            var = ds[name][variable]
            qc = np.ma.asarray(var[:])
            if qc.shape != shape or var.dimensions != dimensions[0]:
                raise ValueError(f'QC dimensions/shapes differ: {name}')
            valid &= ~np.ma.getmaskarray(qc) & (qc.filled(1) == 0)
        n = int(valid.sum())
        if n == 0:
            raise ValueError('No paired finite observations accepted by QC')
        observed, background, analysis = [a.data[valid] for a in arrays]
        omb, oma = observed - background, observed - analysis
        return {'variable': variable, 'units': units[0], 'n': n, 'qc_groups': qcs,
                'selection': 'paired finite unmasked values; intersection of available QC=0',
                'omb_bias': float(omb.mean()), 'oma_bias': float(oma.mean()),
                'omb_rmse': float(np.sqrt(np.mean(omb**2))),
                'oma_rmse': float(np.sqrt(np.mean(oma**2)))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feedback', type=Path)
    parser.add_argument('--variable', default='airTemperature')
    args = parser.parse_args()
    print(json.dumps(paired_feedback(args.feedback, args.variable), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
