#!/usr/bin/env python3
"""Capture small M3 runtime configuration files without changing the reference.

The capture is an inventory, not a scientific validation or a runnable case.
NetCDF, BUFR, covariance data, executables and execution logs are excluded.
Symbolic links to text configuration are read and their actual targets recorded.
Sources, checksums, missing reference directories and read errors are explicit.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tarfile
from datetime import datetime, timezone
from pathlib import Path

CASE_NAMES = (
    'jedi-2018041500-fgat-corrected',
    'mpas-2018041512-fgat-corrected',
    'mpas-2018041418-initial',
    'm3-3days-20180415',
    'm3-native-cycle-3days-20180415',
    'm3-native-cycle-7days-20180415',
)
EXCLUDED_DIRS = {'Data', 'B_Matrix', 'background', 'history', 'logs',
                 'observations', 'failed-attempts'}
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024


def configuration_file(path: Path) -> bool:
    """Select configuration text; never select binary scientific products."""
    return (path.suffix.lower() in {'.yaml', '.yml', '.in', '.xml', '.pbs', '.sh'}
            or path.name.startswith(('streams.', 'namelist.', 'stream_list.'))
            or path.name in {'COMPATIBILITY', 'case-enter.sh'})


def capture(case_root: Path, output: Path) -> tuple[Path, Path]:
    """Save an immutable text snapshot and source manifest in a new directory."""
    case_root, output = case_root.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError(f'Capture destination already exists: {output}; choose a new directory.')
    if not case_root.is_dir():
        raise FileNotFoundError(f'Reference CASE directory does not exist: {case_root}')
    if output == case_root or case_root in output.parents:
        raise ValueError('Capture destination must be outside the reference CASE directory.')

    scopes = [case_root / 'cases' / name for name in CASE_NAMES]
    scopes.extend([case_root / 'runtime-inspection',
                   case_root / 'work/jedi-fgat-corrected',
                   case_root / 'work/mpas-fgat-corrected'])
    records, errors, contents = [], [], []
    seen_files: set[str] = set()
    total_bytes = 0

    def add(path: Path) -> None:
        nonlocal total_bytes
        if not configuration_file(path) or str(path) in seen_files:
            return
        seen_files.add(str(path))
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                raise ValueError('configuration file exceeds 4 MiB capture limit')
            data = path.read_bytes()
            data.decode('utf-8')
            total_bytes += len(data)
            if total_bytes > MAX_TOTAL_BYTES:
                raise RuntimeError('Capture exceeds 64 MiB; inspect the selected reference directories.')
            name = 'files/' + str(path).lstrip('/')
            records.append({'source': str(path), 'resolved': str(path.resolve()),
                            'archive_path': name, 'size_bytes': len(data),
                            'sha256': hashlib.sha256(data).hexdigest()})
            contents.append((name, data))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            errors.append({'source': str(path), 'error': str(error)})

    # Root files include the controlled environment and shared Obs2IODA config.
    for path in sorted(case_root.iterdir()):
        if path.is_file() or path.is_symlink() and not path.is_dir():
            add(path)
    for scope in scopes:
        if not scope.is_dir():
            continue
        seen_dirs: set[str] = set()
        for directory, dirs, files in os.walk(scope, followlinks=True,
                                              onerror=lambda error: errors.append({'error': str(error)})):
            real = str(Path(directory).resolve())
            if real in seen_dirs:
                dirs[:] = []
                continue
            seen_dirs.add(real)
            dirs[:] = sorted(d for d in dirs if not d.startswith('.')
                             and not d.startswith(('before-', 'before_'))
                             and d not in EXCLUDED_DIRS)
            for filename in sorted(files):
                add(Path(directory) / filename)

    report = {'schema_version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
              'reference_root': str(case_root), 'purpose': 'read-only configuration capture',
              'scientifically_validated': False,
              'public_environment': {key: os.environ.get(key) for key in
                                     ('MONAN_JEDI_INSTALL_ROOT', 'STACK_ROOT')},
              'scopes': [{'path': str(p), 'exists': p.is_dir()} for p in scopes],
              'files': records, 'errors': errors, 'configuration_bytes': total_bytes}
    output.mkdir(parents=True)
    manifest = output / 'reference-manifest.json'
    manifest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    archive = output / 'reference-configs.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for name, data in contents:
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o644
            bundle.addfile(info, io.BytesIO(data))
        data = manifest.read_bytes()
        info = tarfile.TarInfo(manifest.name)
        info.size, info.mode = len(data), 0o644
        bundle.addfile(info, io.BytesIO(data))
    return manifest, archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest, archive = capture(args.case_root, args.output)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f'[FAIL] {error}\n')
    report = json.loads(manifest.read_text())
    print(f'[OK] captured {len(report["files"])} configuration files: {archive}')
    print(f'[INFO] source inventory: {manifest}')
    for scope in report['scopes']:
        print(f'[{"FOUND" if scope["exists"] else "MISSING"}] {scope["path"]}')
    if report['errors']:
        print(f'[WARN] {len(report["errors"])} capture errors recorded in the manifest; capture is incomplete.')
    print('[INFO] No jobs submitted and no reference files modified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
