# 20. validate_mpas_background.py

[Back to tools index](../tools.md) | Previous: [validate_fgat_window.py](19-validate-fgat-window.md) | Next: [validate_saber_inputs.py](21-validate-saber-inputs.md)

## Purpose

`validate_mpas_background.py` validates the staged MPAS background file used by the 3DVar-FGAT experiment.

## Context of use

Run this after staging the MPAS background and before executing JEDI. It checks file presence, size, NetCDF-like extension, optional NetCDF readability, expected state variables, and temporal metadata indicators.

## Location

```text
tools/validate_mpas_background.py
```

## Prerequisites

Python 3, PyYAML, and a configured data root. Optional NetCDF parsing uses `netCDF4` or `xarray` when available.

## How to run

```bash
python tools/validate_mpas_background.py [--background FILE] [--layout FILE] [--render-context FILE] [--data-root ROOT] [--strict]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `--background` | Explicit MPAS background file. |
| `--layout` | Data layout used to infer the background path. |
| `--render-context` | Context used to read expected JEDI state variables. |
| `--data-root` | Root used for relative paths. Defaults to `MONAN_DATA_ROOT`. |
| `--strict` | Fails on missing files, invalid extension, missing variables, or missing time metadata. |

## Inputs and outputs

The tool prints background file status, file size, variable count, matched JEDI variables, and detected temporal metadata. It does not validate full MPAS scientific consistency.

## Examples

```bash
python tools/validate_mpas_background.py
```

```bash
python tools/validate_mpas_background.py --background /data/monan/background/mpasout.nc --strict
```

## Common errors

- Data root is missing or unresolved.
- Background path cannot be determined from the layout.
- Background file missing, empty, or not NetCDF-like.
- Expected JEDI state variables are not found directly or via aliases.

## Related tools

Use after [`validate_file_formats.py`](08-validate-file-formats.md) and before [`run_variational.py`](25-run-variational.md).

[Back to tools index](../tools.md) | Previous: [validate_fgat_window.py](19-validate-fgat-window.md) | Next: [validate_saber_inputs.py](21-validate-saber-inputs.md)
