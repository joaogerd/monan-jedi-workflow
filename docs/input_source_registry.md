# Real input source registry

This document describes the real input source registry for the first MONAN/JEDI 3DVar-FGAT case.

The registry records where each scientific file comes from before it is staged into
`${MONAN_EXTERNAL_DATA_ROOT}` and later linked or copied into `${MONAN_DATA_ROOT}`.

## Files

Registry:

```text
configs/experiments/3dvar_fgat/input_sources.example.yaml
```

Auditor:

```text
tools/audit_input_sources.py
```

Wrapper:

```text
scripts/setup/audit_3dvar_fgat_input_sources.sh
```

## Purpose

The registry makes the provenance of each input explicit:

- source path;
- target path in the external input root;
- target path in the staged data root;
- origin system;
- owner/contact;
- discovery status;
- notes.

This avoids undocumented manual copies and makes the first scientific experiment reproducible.

## Audit

```bash
bash scripts/setup/audit_3dvar_fgat_input_sources.sh
```

The default audit reports empty or pending sources without failing.

## Strict audit

```bash
bash scripts/setup/audit_3dvar_fgat_input_sources.sh --strict
```

Strict mode fails if required `source_path` entries are empty or point to missing files. It also
checks the MPAS-JEDI build root and variational executable paths.

Use strict mode only after filling real paths.

## Suggested workflow

1. Copy the example registry if needed:

```bash
cp configs/experiments/3dvar_fgat/input_sources.example.yaml \
   configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

2. Fill `source_path` for each real input.
3. Fill `owner_or_contact` and `origin_system` fields.
4. Run:

```bash
bash scripts/setup/audit_3dvar_fgat_input_sources.sh \
  configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

5. When all required sources exist, run strict mode:

```bash
bash scripts/setup/audit_3dvar_fgat_input_sources.sh --strict \
  configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

6. Use the registry to populate `${MONAN_EXTERNAL_DATA_ROOT}`.

## Current boundary

This registry does not move files by itself. It records where files are expected to come from.
Actual staging is still handled by:

```text
scripts/setup/stage_3dvar_fgat_inputs.sh
```
