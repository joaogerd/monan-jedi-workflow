# Template rendering layer

MONAN-JEDI-WORKFLOW is moving toward explicit, testable template rendering instead of hidden
string substitution embedded in C-shell task scripts.

This does not replace all behavior from upstream `PrepJEDI.csh`. It only introduces the first
small layer needed to render JEDI/MPAS configuration files from YAML context files.

## Why this layer exists

The upstream MPAS-Workflow performs important substitutions while preparing JEDI applications,
MPAS namelists and stream files. Much of that behavior is embedded in C-shell scripts and generated
`config/auto/*.csh` files.

For MONAN/JACI, we want:

- explicit YAML context files;
- repeatable rendering outside Cylc;
- simple smoke tests that do not require MPAS/JEDI executables;
- clear failure when required placeholders are missing;
- no accidental activation of NCAR/Derecho paths.

## Tool

```bash
tools/render_template.py TEMPLATE --context CONTEXT.yaml --output OUTPUT
```

Supported placeholders:

| Syntax | Source |
|---|---|
| `{{name}}` | YAML context key |
| `{{section.name}}` | Nested YAML key using dot notation |
| `${NAME}` | Environment variable, or YAML key if provided |

By default, unresolved placeholders fail with exit code 2.

For partial templates or smoke tests:

```bash
tools/render_template.py template.yaml \
  --context context.yaml \
  --output rendered.yaml \
  --allow-env \
  --allow-unresolved
```

## 3DVar-FGAT render wrapper

The current wrapper is:

```bash
scripts/run/render_3dvar_fgat.sh
```

Default input:

```text
configs/jedi/applications/3dvar_fgat.yaml
configs/experiments/3dvar_fgat/render_context.example.yaml
```

Default output:

```text
build/rendered/3dvar_fgat.yaml
```

Run:

```bash
scripts/run/render_3dvar_fgat.sh
```

## Current limitations

This layer does not yet:

- generate observation blocks from `ObsPlugs`;
- build MPAS namelists or streams;
- link graph partition files;
- link invariant files;
- resolve cycle-specific directories;
- validate JEDI schema;
- validate MPAS stream semantics;
- run `mpasjedi_variational.x`.

Those behaviors are part of the future replacement or adaptation of upstream `PrepJEDI.csh`.

## Development rule

Every new template introduced into `configs/` should have:

1. a context example;
2. a render command;
3. a smoke-test assertion;
4. documented provenance when derived from upstream.
