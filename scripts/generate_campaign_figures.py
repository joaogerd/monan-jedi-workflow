#!/usr/bin/env python3
"""Produce the three M3 campaign evidence figures from a completed native case.

Reads validation manifests, SQLite state, JEDI logs and UFO feedback files.
Never submits jobs or changes the campaign. Outputs PNG/PDF/SVG, CSV and a
Markdown summary. A new output directory is required to preserve old evidence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import netCDF4
import numpy as np
import yaml

NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?'
QUADRATIC = re.compile(r'Quadratic cost function:\s*J\s*\(\s*(\d+)\s*\)\s*=\s*(' + NUMBER + ')')
NONLINEAR = re.compile(r'CostFunction:\s*Nonlinear J\s*=\s*(' + NUMBER + ')')


def parse_cost(text):
    """Extract one outer loop's J0 and quadratic inner costs, excluding Jb/JoJc."""
    values = []
    initial = None
    for line in text.splitlines():
        start = NONLINEAR.search(line)
        if start and not values:
            initial = float(start[1].replace('D', 'e').replace('d', 'e'))
        match = QUADRATIC.search(line)
        if not match:
            continue
        iteration = int(match[1])
        value = float(match[2].replace('D', 'e').replace('d', 'e'))
        if values and iteration <= values[-1][0]:
            raise ValueError('multiple/repeated outer minimizations in log; select an outer loop explicitly')
        values.append((iteration, value))
    if not values or (values[0][0] != 0 and initial is None):
        raise ValueError('initial nonlinear J or quadratic J iterations missing from JEDI log')
    if values[0][0] != 0:
        values.insert(0, (0, initial))
    if not all(np.isfinite(value) and value >= 0 for _, value in values) or values[0][1] <= 0:
        raise ValueError('invalid/nonfinite cost function values')
    return values


def observation_stats(paths):
    """Calculate paired O-B/O-A metrics on identical finite, QC=0 samples.

    If numbered QC groups exist, intersect all available EffectiveQC0/1 masks;
    otherwise use EffectiveQC. Missing QC never silently disables filtering.
    NetCDF missing values are masked before arithmetic. All pressure levels are
    included, matching the unbinned radiosonde temperature figure in M3.
    """
    omb, oma, selected_groups = [], [], set()
    for path in paths:
        with netCDF4.Dataset(path) as handle:
            def read(group):
                try:
                    variable = handle.groups[group].variables['airTemperature']
                except KeyError as error:
                    raise ValueError(f'{path}: missing {group}/airTemperature; groups={list(handle.groups)}') from error
                return np.ma.asarray(variable[:], dtype=float).filled(np.nan)
            observed, background, analysis = (read(g) for g in ('ObsValue', 'hofx0', 'hofx1'))
            if observed.shape != background.shape or observed.shape != analysis.shape:
                raise ValueError(f'{path}: incompatible observation/HofX shapes')
            mask = np.isfinite(observed) & np.isfinite(background) & np.isfinite(analysis)
            # IODA float missing sentinel, including files without _FillValue.
            mask &= (np.abs(observed) < 1e30) & (np.abs(background) < 1e30) & (np.abs(analysis) < 1e30)
            groups = [g for g in ('EffectiveQC0', 'EffectiveQC1') if g in handle.groups]
            if not groups and 'EffectiveQC' in handle.groups:
                groups = ['EffectiveQC']
            if not groups:
                raise ValueError(f'{path}: missing EffectiveQC groups; available={list(handle.groups)}')
            for group in groups:
                qc = read(group)
                if qc.shape != observed.shape:
                    raise ValueError(f'{path}: incompatible QC shape in {group}')
                mask &= qc == 0
                selected_groups.add(group)
            omb.append((observed[mask] - background[mask]).ravel())
            oma.append((observed[mask] - analysis[mask]).ravel())
    b, a = np.concatenate(omb), np.concatenate(oma)
    if not b.size:
        raise ValueError('no paired finite QC=0 radiosonde temperatures')
    return {'nobs': int(b.size), 'omb_bias': float(b.mean()), 'oma_bias': float(a.mean()),
            'omb_rmse': float(np.sqrt(np.mean(b*b))), 'oma_rmse': float(np.sqrt(np.mean(a*a))),
            'qc_groups': '+'.join(sorted(selected_groups))}


def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError(f'timestamp must have UTC offset: {value}')
    return parsed.astimezone(timezone.utc)


def valid_manifest(path, cycle_id):
    data = json.loads(path.read_text())
    if data.get('valid') is not True or data.get('cycle_id') != cycle_id:
        raise ValueError(f'invalid or wrong-cycle validation: {path}')
    return data


def collect(case):
    request = yaml.safe_load((case / 'campaign-request.yaml').read_text())['campaign']
    start, end = utc(request['start']), utc(request['end'])
    step = timedelta(hours=request['cycle_interval_hours'])
    dates = []
    when = start
    while when <= end:
        dates.append(when)
        when += step
    with sqlite3.connect((case / '.simpleworkflow/state.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        state = db.execute('select cycle_id, task, status from task_state').fetchall()
        bad = [row for row in state if row[2] != 'success']
        if bad:
            raise ValueError(f'workflow has non-success final task states: {bad[:8]}')
        expected = {date.strftime('%Y%m%dT%H%M%SZ') for date in dates}
        if {row[0] for row in state if row[0]} != expected:
            raise ValueError('workflow cycles do not match the requested period')
        runs = db.execute('select count(*) from run_history').fetchone()[0]
        attempts = db.execute('select count(*) from attempt_history').fetchone()[0]
    convergence, observations, curves, sources = [], [], {}, []
    for index, date in enumerate(dates):
        cid = date.strftime('%Y%m%dT%H%M%SZ')
        run = case / 'work/jedi' / cid
        manifest = valid_manifest(run / '.monan-jedi-workflow/jedi-validation.json', cid)
        log = Path(manifest['log'])
        text = log.read_text(errors='replace')
        if 'OOPS Ending' not in text:
            raise ValueError(f'{log}: OOPS Ending missing')
        curve = parse_cost(text)
        curves[cid] = curve
        js = [j for _, j in curve]
        convergence.append({'cycle': cid, 'iterations': curve[-1][0], 'J_initial': js[0],
                            'J_final': js[-1], 'reduction_percent': 100*(1-js[-1]/js[0]),
                            'monotonic': bool(np.all(np.diff(js) <= 0)), 'oops_ending': True})
        feedback = sorted((run / 'Data/os').glob('*sondes*.nc*'))
        if not feedback:
            raise ValueError(f'{run}/Data/os: radiosonde feedback files missing')
        observations.append({'cycle': cid, **observation_stats(feedback)})
        sources.append({'cycle': cid, 'log': str(log), 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
                        'feedback': [str(path) for path in feedback]})
        valid_manifest(case / 'work/obs' / date.strftime('%Y%m%d%H') /
                       '.monan-jedi-workflow/obs2ioda-validation.json', cid)
        if index < len(dates)-1:
            valid_manifest(case / 'work/mpas' / cid / '.monan-jedi-workflow/mpas-validation.json', cid)
        print(f'[OK] cycle {index+1}/{len(dates)} {cid}: J and paired radiosonde diagnostics', flush=True)
    summary = {'campaign': str(case), 'start': start.isoformat(), 'end': end.isoformat(),
               'duration_hours': (end-start).total_seconds()/3600, 'cycles': len(dates),
               'forecast_legs': len(dates)-1, 'workflow_tasks': len(state), 'workflow_success': len(state),
               'workflow_runs': runs, 'workflow_attempts': attempts,
               'obs2ioda_conversions': sum(task == 'observations_run' for _, task, _ in state),
               'all_monotonic': all(row['monotonic'] for row in convergence),
               'mean_J_reduction_percent': float(np.mean([row['reduction_percent'] for row in convergence])),
               'mean_omb_rmse': float(np.mean([row['omb_rmse'] for row in observations])),
               'mean_oma_rmse': float(np.mean([row['oma_rmse'] for row in observations])),
               'oma_le_omb_cycles': sum(row['oma_rmse'] <= row['omb_rmse'] for row in observations),
               'aggregation': 'arithmetic mean of per-cycle RMSE, not pooled RMSE',
               'observation_selection': 'identical finite samples; intersection of available EffectiveQC0/1=0, or EffectiveQC=0',
               'sources': sources}
    return dates, convergence, observations, curves, summary


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def figures(output, dates, observations, curves):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})
    directory = output / 'figures'
    directory.mkdir()
    title = f'MONAN-JEDI | {dates[0]:%d/%m/%Y}–{dates[-1]:%d/%m/%Y} | UTC'
    def save(fig, name):
        fig.tight_layout()
        for extension in ('png', 'pdf', 'svg'):
            fig.savefig(directory / f'{name}.{extension}', dpi=200, bbox_inches='tight')
        plt.close(fig)
    def time_axis(ax):
        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m', tz=timezone.utc))
        ax.set_xlabel('Data (UTC)')
        ax.grid(alpha=.2)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.step(dates, np.arange(1, len(dates)+1), where='post', marker='o', ms=4, label='Análises JEDI validadas')
    ax.step(dates[1:], np.arange(1, len(dates)), where='post', marker='s', ms=3, label='Previsões entre ciclos validadas')
    ax.set(title=title+'\nConclusão dos ciclos', ylabel='Número acumulado')
    ax.legend(); time_axis(ax); save(fig, 'campaign_completion')
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = plt.cm.viridis(np.linspace(0, 1, len(curves)))
    for color, (cid, curve) in zip(colors, curves.items()):
        ax.plot([i for i, _ in curve], [j/curve[0][1] for _, j in curve], color=color, alpha=.75, lw=1.3)
    ax.set(title=title+'\nConvergência da minimização — uma curva por ciclo',
           xlabel='Iteração interna (0 = estado inicial)', ylabel='J/J₀')
    ax.grid(alpha=.2); save(fig, 'jedi_cost_convergence')
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(dates, [r['omb_rmse'] for r in observations], 'o-', ms=4, label='O−B')
    ax.plot(dates, [r['oma_rmse'] for r in observations], 's-', ms=4, label='O−A')
    ax.set(title=title+'\nRadiossondas — temperatura do ar (mesma amostra, QC=0)', ylabel='RMSE (K)')
    ax.legend(); time_axis(ax); save(fig, 'omb_oma_rmse_airTemperature')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', type=Path, help='materialized campaign directory containing campaign-request.yaml')
    parser.add_argument('--output', type=Path, help='new output directory; default: CAMPAIGN/diagnostics')
    args = parser.parse_args()
    case = args.campaign.expanduser().resolve()
    output = (args.output or case / 'diagnostics').expanduser().resolve()
    try:
        if output.exists():
            raise ValueError(f'output already exists: {output}; choose a new --output to preserve evidence')
        dates, convergence, observations, curves, summary = collect(case)
        output.mkdir(parents=True)
        write_csv(output / 'jedi_convergence.csv', convergence)
        write_csv(output / 'jedi_cost_iterations.csv', [{'cycle': cid, 'iteration': i, 'J': j, 'J_normalized': j/curve[0][1]}
                  for cid, curve in curves.items() for i, j in curve])
        write_csv(output / 'omb_oma_sondes_airTemperature.csv', observations)
        write_csv(output / 'campaign_summary.csv', [{'metric': key, 'value': value} for key, value in summary.items() if key != 'sources'])
        (output / 'diagnostic_summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False)+'\n')
        figures(output, dates, observations, curves)
        report = (f'# MONAN-JEDI — campanha de {summary["duration_hours"]:g} h\n\n'
                  f'{summary["start"]} → {summary["end"]}\n\n'
                  f'- Análises: {summary["cycles"]}; previsões entre ciclos: {summary["forecast_legs"]}.\n'
                  f'- Estados success no workflow: {summary["workflow_success"]}.\n'
                  f'- J monotônico em todos os ciclos: {summary["all_monotonic"]}.\n'
                  f'- Redução média de J: {summary["mean_J_reduction_percent"]:.2f}%.\n'
                  f'- RMSE médio O−B: {summary["mean_omb_rmse"]:.4f} K; O−A: {summary["mean_oma_rmse"]:.4f} K.\n'
                  f'- O−A ≤ O−B: {summary["oma_le_omb_cycles"]}/{summary["cycles"]} ciclos.\n\n'
                  'RMSE médio é a média aritmética dos RMSEs dos ciclos, como no relatório M3. '
                  'O−B e O−A usam a mesma amostra finita e aprovada nos grupos QC registrados nos CSVs. '
                  'O QC exato do script histórico de 2018 não está documentado nos CSVs arquivados; '
                  'comparação numérica entre anos exige conferir essa seleção. '
                  'Estas observações participaram da assimilação: o diagnóstico mede consistência e ajuste, '
                  'não verificação independente de previsões.\n\n')
        for name in ('campaign_completion', 'jedi_cost_convergence', 'omb_oma_rmse_airTemperature'):
            report += f'![{name}](figures/{name}.png)\n\n'
        (output / 'report.md').write_text(report)
        print(f'[OK] figures, CSVs and report: {output}')
        print(json.dumps({k: v for k, v in summary.items() if k != 'sources'}, indent=2, ensure_ascii=False))
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        parser.exit(2, f'[FAIL] campaign figures: {error}\n')


if __name__ == '__main__':
    main()
