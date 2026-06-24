from __future__ import annotations

import sys
from pathlib import Path

from monan_jedi_workflow.obs2ioda_stage import prepare_obs2ioda, run_obs2ioda


def test_obs2ioda_stage_prepares_and_runs_cycle_converter(tmp_path: Path) -> None:
    config_dir = tmp_path / "experiment"
    (config_dir / "inputs").mkdir(parents=True)
    (config_dir / "inputs/20180415T000000Z.bufr").write_bytes(b"bufr")
    (config_dir / "obs2ioda.yaml").write_text(
        f"""obs2ioda:
  work_dir: work/obs2ioda/{{cycle_id}}
  converters:
    - name: sample
      inputs: [inputs/{{cycle_id}}.bufr]
      outputs: ["{{work_dir}}/sample.nc4"]
      argv:
        - {sys.executable}
        - -c
        - "from pathlib import Path; Path(r'{{work_dir}}/sample.nc4').write_bytes(b'ioda')"
""",
        encoding="utf-8",
    )

    run = prepare_obs2ioda(config_dir, "2018-04-15T00:00:00Z")
    assert run.manifest_path.exists()

    manifest = run_obs2ioda(config_dir, "2018-04-15T00:00:00Z")
    assert manifest.exists()
    assert (run.work_dir / "sample.nc4").read_bytes() == b"ioda"

    assert run_obs2ioda(config_dir, "2018-04-15T00:00:00Z") == manifest
