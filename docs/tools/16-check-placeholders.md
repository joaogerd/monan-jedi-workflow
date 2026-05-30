# 16. check_placeholders.py

[Back to tools index](../tools.md) | Previous: [validate_jedi_observer_config.py](15-validate-jedi-observer-config.md) | Next: [render_template.py](17-render-template.md)

## Purpose

`check_placeholders.py` scans configuration files and templates for unresolved placeholder tokens such as `{{name}}` and `${NAME}`.

## Context of use

Use this before or after rendering templates to inspect which symbolic values remain in configuration files. It is an inspection tool, not a failure gate.

## Location

```text
tools/check_placeholders.py
```

## Prerequisites

Python 3. No external YAML parser is required because the tool scans text files.

## How to run

```bash
python tools/check_placeholders.py [paths...]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `paths` | Files or directories to inspect. Defaults to `configs`. |

## Inputs and outputs

Directories are searched recursively for files with suffixes such as `.yaml`, `.yml`, `.template`, `.env`, and `.example`. The tool prints each file with detected placeholders. It returns `0` even when placeholders are found.

## Examples

```bash
python tools/check_placeholders.py
```

```bash
python tools/check_placeholders.py configs templates
```

## Common messages

- `No placeholders found.` means the scanned files had no matching placeholder tokens.
- A listed placeholder may be intentional if the file is a template or example.

## Related tools

Use with [`render_template.py`](17-render-template.md), [`render_observers.py`](14-render-observers.md), and [`validate_experiment.py`](18-validate-experiment.md).

[Back to tools index](../tools.md) | Previous: [validate_jedi_observer_config.py](15-validate-jedi-observer-config.md) | Next: [render_template.py](17-render-template.md)
