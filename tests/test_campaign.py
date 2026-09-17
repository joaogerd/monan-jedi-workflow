from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from monan_jedi_workflow import campaign
from monan_jedi_workflow.campaign import (
    CampaignSpec,
    PreflightItem,
    PreflightReport,
    load_campaign_spec,
    preflight_campaign,
    run_campaign,
)
from monan_jedi_workflow.stage_config import StageConfigurationError


def _spec(tmp_path: Path) -> CampaignSpec:
    return CampaignSpec(
        config_path=tmp_path / "campaign.yaml",
        name="m3-3days-20180415",
        start_cycle="2018-04-15T00:00:00Z",
        end_cycle="2018-04-18T00:00:00Z",
        duration_hours=72,
        destination=tmp_path / "run",
        cycling_jedi_case=tmp_path / "cycling",
        initial_mpas_case=tmp_path / "initial-mpas",
        mpas_case=tmp_path / "mpas",
        obs2ioda_config=tmp_path / "obs2ioda.yaml",
        swf_command=("swf",),
        initial_jedi_case=tmp_path / "legacy-initial",
    )


def test_load_campaign_spec_resolves_profile_environment_and_duration(
    tmp_path: Path, monkeypatch,
) -> None:
    case = tmp_path / "CASE"
    case.mkdir()
    monkeypatch.setenv("CASE", str(case))

    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    profile = profile_dir / "jaci.yaml"
    profile.write_text(
        yaml.safe_dump(
            {
                "profile": {
                    "initial_jedi_case": "${CASE}/cases/initial",
                    "cycling_jedi_case": "${CASE}/cases/cycling",
                    "initial_mpas_case": "${CASE}/cases/initial-mpas",
                    "mpas_case": "${CASE}/cases/mpas",
                    "obs2ioda_config": "${CASE}/obs2ioda.yaml",
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    config = tmp_path / "campaign.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "campaign": {
                    "name": "m3-3days-20180415",
                    "start": "2018-04-15T00:00:00Z",
                    "duration": "PT72H",
                    "destination": "${CASE}/cases/m3-3days-20180415",
                },
                "profile": "profiles/jaci.yaml",
                "forecast": {"run_on_last_cycle": True},
                "execution": {"swf_command": "swf"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    spec = load_campaign_spec(config)

    assert spec.start_cycle == "2018-04-15T00:00:00Z"
    assert spec.end_cycle == "2018-04-18T00:00:00Z"
    assert spec.duration_hours == 72
    assert spec.destination == case / "cases/m3-3days-20180415"
    assert spec.initial_jedi_case == case / "cases/initial"
    assert spec.initial_mpas_case == case / "cases/initial-mpas"
    assert spec.run_mpas_on_last_cycle is True
    assert spec.swf_command == ("swf",)


def test_load_campaign_spec_resolves_case_root_without_environment(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.delenv("CASE", raising=False)
    case = tmp_path / "CASE"
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    profile = profile_dir / "jaci.yaml"
    profile.write_text(
        yaml.safe_dump(
            {
                "profile": {
                    "case_root": "../CASE",
                    "initial_jedi_case": "cases/initial",
                    "cycling_jedi_case": "cases/cycling",
                    "initial_mpas_case": "cases/initial-mpas",
                    "mpas_case": "cases/mpas",
                    "obs2ioda_config": "obs2ioda.yaml",
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    config = tmp_path / "campaign.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "campaign": {
                    "name": "m3-3days-20180415",
                    "start": "2018-04-15T00:00:00Z",
                    "duration": "PT72H",
                    "destination": "cases/m3-3days-20180415",
                },
                "profile": "profiles/jaci.yaml",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    spec = load_campaign_spec(config)

    assert spec.destination == case / "cases/m3-3days-20180415"
    assert spec.initial_jedi_case == case / "cases/initial"
    assert spec.cycling_jedi_case == case / "cases/cycling"
    assert spec.initial_mpas_case == case / "cases/initial-mpas"
    assert spec.mpas_case == case / "cases/mpas"
    assert spec.obs2ioda_config == case / "obs2ioda.yaml"
    assert spec.run_mpas_on_last_cycle is False


def test_initial_jedi_case_is_optional_for_compact_campaign(tmp_path: Path) -> None:
    config = tmp_path / "campaign.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "campaign": {
                    "name": "native-cycle",
                    "start": "2018-04-15T00:00:00Z",
                    "duration": "PT6H",
                    "destination": str(tmp_path / "run"),
                },
                "profile": {
                    "cycling_jedi_case": str(tmp_path / "cycling"),
                    "initial_mpas_case": str(tmp_path / "initial-mpas"),
                    "mpas_case": str(tmp_path / "mpas"),
                    "obs2ioda_config": str(tmp_path / "obs2ioda.yaml"),
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    spec = load_campaign_spec(config)
    assert spec.initial_jedi_case is None


def test_initial_mpas_case_is_required(tmp_path: Path) -> None:
    config = tmp_path / "campaign.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "campaign": {
                    "name": "missing-initial-mpas",
                    "start": "2018-04-15T00:00:00Z",
                    "duration": "PT6H",
                    "destination": str(tmp_path / "run"),
                },
                "profile": {
                    "cycling_jedi_case": str(tmp_path / "cycling"),
                    "mpas_case": str(tmp_path / "mpas"),
                    "obs2ioda_config": str(tmp_path / "obs2ioda.yaml"),
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(StageConfigurationError, match="initial_mpas_case"):
        load_campaign_spec(config)


@pytest.mark.parametrize("value", ["$CASE/cases/run", "${CASE}/cases/run"])
def test_load_campaign_spec_rejects_undefined_environment_variable(
    tmp_path: Path, monkeypatch, value: str
) -> None:
    monkeypatch.delenv("CASE", raising=False)
    config = tmp_path / "campaign.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "campaign": {
                    "name": "undefined-env",
                    "start": "2018-04-15T00:00:00Z",
                    "duration": "PT6H",
                    "destination": value,
                },
                "profile": {
                    "cycling_jedi_case": str(tmp_path / "cycling"),
                    "initial_mpas_case": str(tmp_path / "initial-mpas"),
                    "mpas_case": str(tmp_path / "mpas"),
                    "obs2ioda_config": str(tmp_path / "obs2ioda.yaml"),
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(StageConfigurationError, match=r"\$(?:CASE|\{CASE\})"):
        load_campaign_spec(config)


def test_load_campaign_spec_accepts_unquoted_yaml_timestamps(tmp_path: Path) -> None:
    config = tmp_path / "campaign.yaml"
    config.write_text(
        f"""campaign:
  name: timestamp-test
  start: 2018-04-15T00:00:00Z
  end: 2018-04-18T00:00:00Z
  destination: {tmp_path / 'run'}

profile:
  cycling_jedi_case: {tmp_path / 'cycling'}
  initial_mpas_case: {tmp_path / 'initial-mpas'}
  mpas_case: {tmp_path / 'mpas'}
  obs2ioda_config: {tmp_path / 'obs2ioda.yaml'}
""",
        encoding="utf-8",
    )

    spec = load_campaign_spec(config)

    assert spec.start_cycle == "2018-04-15T00:00:00Z"
    assert spec.end_cycle == "2018-04-18T00:00:00Z"
    assert spec.duration_hours == 72


def test_forecast_mapping_rejects_unknown_fields(tmp_path: Path) -> None:
    config = tmp_path / "campaign.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "campaign": {
                    "name": "forecast-test",
                    "start": "2018-04-15T00:00:00Z",
                    "duration": "PT6H",
                    "destination": str(tmp_path / "run"),
                },
                "profile": {
                    "cycling_jedi_case": str(tmp_path / "cycling"),
                    "initial_mpas_case": str(tmp_path / "initial-mpas"),
                    "mpas_case": str(tmp_path / "mpas"),
                    "obs2ioda_config": str(tmp_path / "obs2ioda.yaml"),
                },
                "forecast": {"expression": "cycle_is_last or whatever"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(StageConfigurationError, match="unsupported"):
        load_campaign_spec(config)


def test_preflight_checks_observations_for_first_and_all_following_cycles(
    tmp_path: Path, monkeypatch,
) -> None:
    spec = _spec(tmp_path)
    for directory in (
        spec.cycling_jedi_case,
        spec.initial_mpas_case,
        spec.mpas_case,
        spec.initial_jedi_case,
    ):
        assert directory is not None
        directory.mkdir()
    spec.obs2ioda_config.write_text("obs2ioda: {}\n", encoding="utf-8")
    spec.destination.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        campaign,
        "_initial_mpas_detail",
        lambda _: PreflightItem("initial MPAS case", True, "valid"),
    )
    monkeypatch.setattr(campaign, "_command_available", lambda _: True)
    seen: list[str] = []
    missing = tmp_path / "missing-prepbufr"

    def fake_obs_inputs(_config: Path, cycle) -> tuple[list[Path], list[str]]:
        seen.append(campaign._iso(cycle))
        return ([missing] if len(seen) == 1 else [], ["converter"])

    monkeypatch.setattr(campaign, "_rendered_obs_inputs", fake_obs_inputs)

    report = preflight_campaign(spec)

    assert not report.valid
    assert len(seen) == 13
    assert seen[0] == "2018-04-15T00:00:00Z"
    assert seen[-1] == "2018-04-18T00:00:00Z"
    observation = next(
        item for item in report.items if item.label.startswith("observation inputs")
    )
    assert "13 cycles" in observation.label
    assert str(missing) in observation.detail


def test_run_campaign_stops_before_materialization_when_preflight_fails(
    tmp_path: Path, monkeypatch,
) -> None:
    spec = _spec(tmp_path)
    report = PreflightReport(
        spec=spec,
        items=(PreflightItem("observations", False, "missing"),),
    )
    monkeypatch.setattr(campaign, "load_campaign_spec", lambda _: spec)
    monkeypatch.setattr(campaign, "preflight_campaign", lambda _: report)

    called = False

    def fail_if_materialized(_: CampaignSpec) -> Path:
        nonlocal called
        called = True
        raise AssertionError("campaign must not be materialized after failed preflight")

    monkeypatch.setattr(campaign, "materialize_campaign", fail_if_materialized)

    assert run_campaign(tmp_path / "campaign.yaml") == 2
    assert not called


def test_existing_campaign_request_is_reusable_for_restart(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    spec.destination.mkdir()
    spec.workflow_path.write_text("workflow:\n  name: test\n", encoding="utf-8")
    (spec.destination / "campaign-request.yaml").write_text(
        yaml.safe_dump(campaign._request_document(spec), sort_keys=False),
        encoding="utf-8",
    )

    assert campaign.materialize_campaign(spec) == spec.destination
