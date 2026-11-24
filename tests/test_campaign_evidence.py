"""Current campaign.yaml + JEDI log based M3 evidence, never fabricated."""
import json
import sqlite3

import pytest
import yaml

from monan_jedi_workflow.campaign_evidence import (
    collect_evidence, parse_cost, parse_cost_components, render_evidence,
)


def _case(tmp_path):
    root = tmp_path / "case"
    root.mkdir()
    cycles = ["20260130T000000Z", "20260130T060000Z"]
    state = root / ".simpleworkflow" / "state.sqlite3"
    state.parent.mkdir()
    with sqlite3.connect(state) as db:
        db.execute("CREATE TABLE task_state (task TEXT, status TEXT, reason TEXT)")
        db.executemany("INSERT INTO task_state VALUES (?, ?, ?)", [
            ("c00000_jedi_run", "SUCCESS", None),
            ("c00000_mpas_run", "SUCCESS", None),
            ("c00001_jedi_run", "SUCCESS", None)])
    for cycle in cycles:
        run = root / "work" / "jedi" / cycle
        directory = run / ".monan-jedi-workflow"
        directory.mkdir(parents=True)
        log = run / "jedi.stdout.log"
        log.write_text("CostFunction: Nonlinear J = 100\n"
                       "Quadratic cost function: J ( 1) = 80\n"
                       "Quadratic cost function: Jb ( 1) = 10\n"
                       "Quadratic cost function: JoJc ( 1) = 70\n"
                       "Quadratic cost function: J ( 2) = 60\n"
                       "OOPS Ending\n")
        (directory / "jedi-validation.json").write_text(
            json.dumps({"valid": True, "cycle_id": cycle, "log": str(log)}))
    mpas = root / "work" / "mpas" / cycles[0] / ".monan-jedi-workflow"
    mpas.mkdir(parents=True)
    (mpas / "mpas-validation.json").write_text(
        json.dumps({"valid": True, "cycle_id": cycles[0]}))
    return root, cycles


def test_cost_parser_total_quadratic_only():
    curve = parse_cost("CostFunction: Nonlinear J = 100\n"
                       "Quadratic cost function: J ( 1) = 80.0\n"
                       "Quadratic cost function: Jb ( 1) = 12\n"
                       "Quadratic cost function: JoJc ( 1) = 68\n"
                       "Quadratic cost function: J ( 2) = 7D1\n")
    assert curve == [(0, 100.0), (1, 80.0), (2, 70.0)]


def test_cost_parser_rejects_multiple_outer_loops():
    with pytest.raises(ValueError, match="multiple"):
        parse_cost("CostFunction: Nonlinear J = 100\n"
                   "Quadratic cost function: J ( 1) = 80\n"
                   "Quadratic cost function: J ( 1) = 70\n")


def test_campaign_evidence_complete_and_pngs(tmp_path):
    pytest.importorskip("matplotlib")
    root, cycles = _case(tmp_path)
    result = collect_evidence(root, cycles)
    assert result["campaign_complete"] is True
    assert len(result["convergence"]) == 2
    assert result["workflow"]["tasks_total"] == 3
    assert all(row["monotonic"] for row in result["convergence"])
    assert result["convergence"][0]["reduction_percent"] == pytest.approx(40.0)
    output = root / "diagnostics" / "figures"
    figures = render_evidence(result, output)
    assert figures == ["campaign_completion.png", "jedi_cost_convergence.png",
                       "jedi_cost_components_20260130T000000Z.png"]
    assert all((output / name).stat().st_size > 0 for name in figures)
    assert all((output / name.replace(".png", ".pdf")).stat().st_size > 0 for name in figures)
    assert all((output / name.replace(".png", ".svg")).stat().st_size > 0 for name in figures)
    assert len((output / "jedi_cost_iterations.csv").read_text().splitlines()) == 7
    assert (output / "jedi_cost_components.csv").is_file()


def test_incomplete_cycle_does_not_claim_continuity(tmp_path):
    pytest.importorskip("matplotlib")
    root, cycles = _case(tmp_path)
    (root / "work/mpas" / cycles[0] / ".monan-jedi-workflow/mpas-validation.json").unlink()
    result = collect_evidence(root, cycles)
    assert result["campaign_complete"] is False
    assert any(gap["kind"] == "continuity" for gap in result["gaps"])
    generated = render_evidence(result, root / "diagnostics" / "figures")
    assert "campaign_completion.png" not in generated
    assert "jedi_cost_convergence.png" in generated


def test_missing_or_invalid_log_is_reported_not_fabricated(tmp_path):
    root, cycles = _case(tmp_path)
    (root / "work/jedi" / cycles[1] / "jedi.stdout.log").unlink()
    evidence = collect_evidence(root, cycles)
    assert len(evidence["convergence"]) == 1
    assert any(gap["cycle"] == cycles[1] and gap["kind"] == "cost"
               for gap in evidence["gaps"])


def test_failure_in_sqlite_blocks_complete_campaign(tmp_path):
    root, cycles = _case(tmp_path)
    with sqlite3.connect(root / ".simpleworkflow" / "state.sqlite3") as db:
        db.execute("UPDATE task_state SET status='FAILED' WHERE task='c00001_jedi_run'")
    assert collect_evidence(root, cycles)["campaign_complete"] is False


def test_cost_components_are_not_inferred_when_missing():
    log = ("CostFunction: Nonlinear J = 100\n"
           "Quadratic cost function: J ( 1) = 80\n"
           "Quadratic cost function: Jb ( 1) = 10\n"
           "Quadratic cost function: JoJc ( 1) = 70\n"
           "Quadratic cost function: J ( 2) = 60\n")
    result = parse_cost_components(log, parse_cost(log))
    assert result[0]["Jb"] is None
    assert result[1]["Jb"] == 10
    assert result[1]["JoJc"] == 70
    assert result[2]["Jb"] is None
    assert result[2]["JoJc"] is None
    assert all(r["residual_norm"] is None for r in result)
