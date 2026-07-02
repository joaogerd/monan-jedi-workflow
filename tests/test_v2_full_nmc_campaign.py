"""End-to-end local test for the V2 NMC campaign workflow."""

from __future__ import annotations

import sys
from pathlib import Path

from monan_jedi_workflow.core.stage import RunContext
from monan_jedi_workflow.orchestration.local import LocalWorkflowRunner
from monan_jedi_workflow.platforms.local import LocalProcessBackend
from monan_jedi_workflow.workflows.nmc_campaign import build_nmc_campaign


def _write_programs(workspace: Path) -> None:
    """Write deterministic MPAS-like initialization and forecast fixture programs."""
    init = workspace / "fake_init.py"
    init.write_text(
        """from pathlib import Path
import sys
from netCDF4 import Dataset
path = Path(sys.argv[1]); stamp = sys.argv[2]
path.parent.mkdir(parents=True, exist_ok=True)
with Dataset(path, 'w', format='NETCDF4') as ds:
    ds.createDimension('Time', 1); ds.createDimension('nCells', 2); ds.createDimension('StrLen', 19)
    ds.setncattr('mesh_id', 'x1.10242')
    xtime = ds.createVariable('xtime', 'S1', ('Time', 'StrLen'))
    xtime[0, :] = list(stamp)
print('Initialization complete')
""",
        encoding="utf-8",
    )
    forecast = workspace / "fake_forecast.py"
    forecast.write_text(
        """from pathlib import Path
import sys
from netCDF4 import Dataset
restart, state, stamp = map(Path, sys.argv[1:3]) + ()
""",
        encoding="utf-8",
    )
