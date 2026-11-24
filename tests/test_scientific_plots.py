"""Campaign figures use only real paired JEDI feedback, never synthetic success."""
from pathlib import Path
import json

from netCDF4 import Dataset
import pytest
import yaml

from monan_jedi_workflow.scientific_plots import collect, main


def campaign(tmp_path):
    root = tmp_path / "case"
    root.mkdir()
    (root / "campaign.yaml").write_text(yaml.safe_dump({
        "calendar": {
            "start": "2026-01-30T00:00:00Z",
            "end": "2026-01-30T06:00:00Z",
            "interval": "PT6H",
            "end_inclusive": True,
        }
    }))
    return root


def feedback(root, cycle, name="obsout_3dvar_sondes.nc4", qc=True):
    folder = root / "work" / "jedi" / cycle / "Data" / "os"
    folder.mkdir(parents=True)
    path = folder / name
    with Dataset(path, "w") as ds:
        ds.createDimension("Location", 3)
        data = {"ObsValue": [280, 280, 280], "hofx0": [282, 281, 290],
                "hofx1": [281, 281, 290]}
        if qc:
            data.update({"EffectiveQC0": [0, 0, 0],
                         "EffectiveQC1": [0, 0, 1]})
        for group, values in data.items():
            var = ds.createGroup(group).createVariable(
                "airTemperature", "f8", ("Location",)
            )
            if group not in ("EffectiveQC0", "EffectiveQC1"):
                var.units = "K"
            var[:] = values
    return path


def test_collect_paired_data_and_report_missing_without_fabricating(tmp_path):
    root = campaign(tmp_path)
    feedback(root, "20260130T000000Z")
    report = collect(root)
    assert report["cycles_expected"] == 2
    assert len(report["rows"]) == 1
    row = report["rows"][0]
    assert row["observer"] == "sondes"
    assert row["variable"] == "airTemperature"
    assert row["n"] == 2
    assert row["omb_rmse"] == pytest.approx((2.5) ** .5)
    assert row["oma_rmse"] == 1
    assert len(report["missing"]) == 5


def test_no_feedback_never_claims_plot_success(tmp_path):
    root = campaign(tmp_path)
    assert main([str(root)]) == 2
    report = json.loads((root / "diagnostics/figures/manifest.json").read_text())
    assert report["paired_records"] == 0
    assert report["figures"] == []
    assert len(report["missing"]) == 6


def test_missing_qc_is_skipped_with_reason(tmp_path):
    root = campaign(tmp_path)
    feedback(root, "20260130T000000Z", qc=False)
    report = collect(root)
    assert report["rows"] == []
    assert any("EffectiveQC" in item["error"] for item in report["skipped"])


def test_render_png_csv_and_manifest(tmp_path):
    pytest.importorskip("matplotlib")
    root = campaign(tmp_path)
    feedback(root, "20260130T000000Z")
    feedback(root, "20260130T060000Z")
    assert main([str(root), "--variables", "airTemperature"]) == 0
    out = root / "diagnostics/figures"
    assert (out / "sondes_airTemperature.png").is_file()
    assert (out / "paired_feedback.csv").is_file()
    report = json.loads((out / "manifest.json").read_text())
    assert report["paired_records"] == 2
    assert report["figures"] == ["sondes_airTemperature.png"]
