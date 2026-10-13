#!/usr/bin/env python3
"""Create an isolated 2025 case using the captured, executed M3 text runtime.

The source tutorial supplies observation paths/providers already configured by
the operator. It is never changed. The new case uses the current installation,
shared mesh/B/physics inputs and the exact captured M3 geometry support files.
No jobs are submitted. Scientific execution must be validated on JACI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'examples/m3-reference-assets'
PHYSICS = ['CAM_ABS_DATA.DBL', 'CAM_AEROPT_DATA.DBL', 'GENPARM.TBL', 'LANDUSE.TBL',
           'OZONE_DAT.TBL', 'OZONE_LAT.TBL', 'OZONE_PLEV.TBL', 'RRTMG_LW_DATA',
           'RRTMG_LW_DATA.DBL', 'RRTMG_SW_DATA', 'RRTMG_SW_DATA.DBL', 'SOILPARM.TBL', 'VEGPARM.TBL']


def dump(path: Path, data: dict, comment: str) -> None:
    path.write_text(comment + '\n' + yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def check_external_inputs(case: Path) -> dict:
    """Check declared fixed dependencies without requiring future cycle products."""
    from monan_jedi_workflow.jedi_stage import load_jedi_run
    from monan_jedi_workflow.stage_config import resolve_path
    run = load_jedi_run(case, '2025-09-01T00:00:00Z')
    missing, checked = [], []
    for entry in run.config['links']:
        # Observation IODA files are produced by OBS; future state by initialization.
        if entry['target'].startswith('Data/ufo/') or entry['target'] == 'Data/covariance':
            continue
        path = resolve_path(entry['source'], config_dir=case, context=run.context, label='JEDI fixed input')
        checked.append(str(path))
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(str(path))
    install = Path(run.context['monan_jedi_install_root'])
    for name in ['mpasjedi_variational.x', 'mpas_atmosphere', 'mpas_init_atmosphere', 'obs2ioda_v3', 'ungrib.exe']:
        path = install/'bin'/name
        checked.append(str(path))
        if not path.is_file() or not os.access(path, os.X_OK):
            missing.append(str(path)+' (executable required)')
    launcher = Path(run.config['pbs']['launcher'])
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        missing.append(str(launcher)+' (PALS executable required)')
    bmatrix = Path(run.context['bmatrix_root'])
    for name in ['NICAS', 'HDIAG', 'VBAL']:
        path = bmatrix/name
        if not path.is_dir() or not any(path.iterdir()):
            missing.append(str(path)+' (nonempty directory required)')
    stddev = bmatrix/'HDIAG/mpas.stddev.nc'
    for path in [stddev, Path(run.context['mesh_root'])/'static/x1.10242.invariant.nc']:
        if not path.is_file():
            missing.append(str(path))
            continue
        with path.open('rb') as stream:
            magic = stream.read(8)
        if not (magic.startswith(b'CDF') or magic == b'\x89HDF\r\n\x1a\n'):
            missing.append(str(path)+' (not a NetCDF/HDF5 file; check download/LFS hydration)')
    if missing:
        raise FileNotFoundError('Reference input preflight failed:\n  '+ '\n  '.join(dict.fromkeys(missing)))
    executable = install/'bin/mpasjedi_variational.x'
    digest = hashlib.sha256()
    with executable.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return {'fixed_inputs': checked, 'jedi_executable': str(executable),
            'jedi_executable_sha256': digest.hexdigest(), 'scientifically_validated': False}


def create_case(source: Path, destination: Path, *, check_inputs: bool = True) -> Path:
    """Materialize a complete new configuration atomically; refuse overwrites."""
    source, destination = source.resolve(), destination.resolve()
    if destination.exists():
        raise FileExistsError(f'Destination already exists: {destination}; use a new case directory.')
    for name in ['obs2ioda.yaml', 'profile.yaml', 'mpas.yaml']:
        if not (source/name).is_file():
            raise FileNotFoundError(f'Source tutorial lacks {name}: {source}')
    proof = json.loads((ASSETS/'provenance.json').read_text())
    for entry in proof['files']:
        path = ASSETS/entry['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError(f'Captured M3 asset checksum mismatch: {path}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='reference-2025-', dir=destination.parent) as temporary:
        case = Path(temporary)/'case'
        shutil.copytree(ROOT/'examples/case', case)
        shutil.copytree(ASSETS/'runtime-skeleton', case/'runtime-skeleton')
        for path in (ASSETS/'templates').iterdir():
            shutil.copy2(path, case/'templates'/path.name)
        # Only the output name changes; the scientific YAML remains the M3 template.
        template = case/'templates/variational.yaml'
        template.write_text(template.read_text().replace('mpas.3dvar.', 'mpas.3dfgat.'))
        # User-selected raw sources/providers are retained, including PREPNR.
        shutil.copy2(source/'obs2ioda.yaml', case/'obs2ioda.yaml')
        profile = yaml.safe_load((source/'profile.yaml').read_text())
        profile['profile'].pop('case_root', None)
        profile['profile'].update(cycling_jedi_case='.', mpas_case='.',
                                  initial_mpas_case='initialization', obs2ioda_config='obs2ioda.yaml')
        dump(case/'profile.yaml', profile, '# Providers copiados do tutorial existente; cases resolvidos neste diretório.')
        config = yaml.safe_load((case/'jedi.yaml').read_text())
        jedi = config['jedi']
        variables = jedi['variables']
        original_mpas = yaml.safe_load((source/'mpas.yaml').read_text())['mpas']
        original_variables = original_mpas.get('variables', {})
        variables['mesh_root'] = original_variables.get('mesh_root', '/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km')
        variables['physics_root'] = original_variables.get('physics_root', '/p/projetos/monan_das/share/MONAN-JEDI-Data/physics/mpas/files')
        # Keep one mesh/physics selection across JEDI, MPAS and initialization,
        # replacing only scalar values so the stage YAML comments remain intact.
        for relative, section in [('mpas.yaml', 'mpas'), ('initialization/mpas.yaml', 'mpas'),
                                  ('initialization/mpas_init.yaml', 'mpas_init')]:
            path = case/relative
            text = path.read_text()
            document = yaml.compose(text)
            stage = next(value for key, value in document.value if key.value == section)
            node = next(value for key, value in stage.value if key.value == 'variables')
            replacements = [(value.start_mark.index, value.end_mark.index,
                             json.dumps(variables[key.value])) for key, value in node.value
                            if key.value in {'mesh_root', 'physics_root'}]
            for start, end, replacement in sorted(replacements, reverse=True):
                text = text[:start]+replacement+text[end:]
            path.write_text(text)
        original_jedi = yaml.safe_load((source/'jedi.yaml').read_text())['jedi'] if (source/'jedi.yaml').exists() else {}
        variables['bmatrix_root'] = original_jedi.get('variables', {}).get('bmatrix_root', variables['bmatrix_root'])
        jedi['runtime'] = {'skeleton': 'runtime-skeleton'}
        jedi['background']['target'] = 'Data/background/{analysis_yyyymmddhh}/mpasout.{background_mpas_file_time}.nc'
        for entry in jedi['links']:
            entry['target'] = entry['target'].replace('Data/ufo/testinput_tier_1/', 'Data/ufo/')
        jedi['links'].extend([
            {'source': '{mesh_root}/static/x1.10242.invariant.nc', 'target': 'x1.10242.invariant.nc'},
            {'source': '{mesh_root}/partitions/x1.10242.graph.info.part.128', 'target': 'x1.10242.graph.info.part.128'},
            *[{'source': '{physics_root}/'+name, 'target': name} for name in PHYSICS],
        ])
        jedi['templates'] = [{'source': 'templates/variational.yaml', 'target': 'variational.yaml'}]
        for suffix in ('outer', 'inner'):
            jedi['templates'].extend([
                {'source': f'templates/namelist.atmosphere.{suffix}.in',
                 'target': 'geometry/{analysis_yyyymmddhh}/namelist.atmosphere.'+suffix},
                {'source': f'templates/streams.atmosphere.jedi.{suffix}.in',
                 'target': 'geometry/{analysis_yyyymmddhh}/streams.atmosphere.'+suffix},
            ])
        jedi['nonlinear_trajectory']['outer_namelist'] = 'geometry/{analysis_yyyymmddhh}/namelist.atmosphere.outer'
        jedi['pbs'].update(ncpus=128, mpiprocs=128)
        jedi['pbs']['environment']['GFORTRAN_CONVERT_UNIT'] = 'big_endian:101-200'
        jedi['validation']['required_log_markers'] = [
            'Run: Finishing oops::Variational<MPAS, UFO and IODA observations> with status = 0', 'OOPS Ending']
        jedi['analysis_base_state']['required_variables'] = [
            'pressure_base','pressure_p','qc','qg','qi','qr','qs','qv','rho','rho_base','skintemp',
            'smois','surface_pressure','theta','theta_base','tslb','u','uReconstructMeridional','uReconstructZonal','w']
        dump(case/'jedi.yaml', config,
             '# Runtime M3 completo: 128 ranks, namelists outer/inner distintos e tabelas físicas.\n'
             '# Ciência e arquivos pequenos preservados em reference-provenance.json.\n'
             '# B, invariant e física são entradas compartilhadas; observações vêm do stage OBS.\n'
             '# Sem número fixo de variáveis: o estado completo de 2025 é validado pelo seu conteúdo.')
        for name, duration in [('smoke', 'PT6H'), ('7d', 'P7D')]:
            campaign = {'campaign': {'name': 'monan-jedi-20250901-'+name,
                                      'start': '2025-09-01T00:00:00Z', 'duration': duration,
                                      'cycle_interval_hours': 6, 'destination': 'cases/monan-jedi-20250901-'+name},
                        'profile': 'profile.yaml', 'forecast': {'run_on_last_cycle': False},
                        'execution': {'swf_command': 'swf'}}
            filename = 'campaign.yaml' if name == 'smoke' else 'campaign-7d.yaml'
            dump(case/filename, campaign, '# Dois ciclos de continuidade.' if name == 'smoke' else '# Liberar somente depois do teste de continuidade validado.')
        proof['adaptation'] = {'start': '2025-09-01T00:00:00Z', 'source_tutorial': str(source),
                               'jedi_ranks': 128, 'output_prefix': 'mpas.3dfgat', 'status': 'not scientifically validated'}
        proof['inputs_check'] = check_external_inputs(case) if check_inputs else {'status': 'not run'}
        (case/'reference-provenance.json').write_text(json.dumps(proof, indent=2)+'\n')
        (case/'README.md').write_text(
            '# Referência M3 adaptada para setembro de 2025\n\n'
            'campaign.yaml: duas análises (00Z e 06Z), inicialização e uma previsão entre ciclos.\n'
            'campaign-7d.yaml: 29 análises; usar somente após validar o teste inicial.\n'
            'runtime-skeleton contém somente os arquivos pequenos da referência capturada.\n'
            'Entradas grandes são links aos dados compartilhados. Nenhum dado de 2018 é reutilizado.\n'
            'Os namelists inner e outer são distintos, conforme a execução original.\n'
            'Verifique a validação científica na JACI; a criação do case não a substitui.\n')
        os.replace(case, destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    args = parser.parse_args()
    try:
        path = create_case(args.source, args.destination)
    except (OSError, ValueError) as error:
        parser.exit(2, f'[FAIL] {error}\n')
    print(f'[OK] new complete reference case: {path}')
    print('[OK] fixed external inputs checked; scientific execution is pending.')
    print(f'[NEXT] monan-jedi-workflow campaign check {path}/campaign.yaml')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
