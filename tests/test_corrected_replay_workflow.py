from pathlib import Path

import yaml


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / "examples/simpleworkflow/cycled_da/corrected-replay-20180415.workflow.yaml.example"
)


def _tasks() -> dict[str, dict]:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert "cycle" not in document
    return {task["name"]: task for task in document["tasks"]}


def test_corrected_replay_has_explicit_cross_cycle_dependencies() -> None:
    tasks = _tasks()

    assert tasks["mpas00_prepare"]["depends_on"] == ["jedi00_gate"]
    assert tasks["obs06_doctor"]["depends_on"] == ["jedi00_gate"]
    assert set(tasks["jedi06_prepare"]["depends_on"]) == {
        "mpas00_gate",
        "obs06_gate",
    }

    assert tasks["mpas06_prepare"]["depends_on"] == ["jedi06_gate"]
    assert tasks["obs12_doctor"]["depends_on"] == ["jedi06_gate"]
    assert set(tasks["jedi12_prepare"]["depends_on"]) == {
        "mpas06_gate",
        "obs12_gate",
    }

    assert tasks["mpas12_prepare"]["depends_on"] == ["jedi12_gate"]
    assert tasks["obs18_doctor"]["depends_on"] == ["jedi12_gate"]
    assert set(tasks["jedi18_prepare"]["depends_on"]) == {
        "mpas12_gate",
        "obs18_gate",
    }


def test_corrected_replay_omits_out_of_scope_first_and_terminal_stages() -> None:
    tasks = _tasks()

    assert not any(name.startswith("obs00_") for name in tasks)
    assert not any(name.startswith("mpas18_") for name in tasks)
    assert "jedi00_prepare" in tasks
    assert "jedi18_gate" in tasks


def test_corrected_replay_validation_gates_are_content_fingerprinted() -> None:
    tasks = _tasks()
    gates = [name for name in tasks if name.endswith("_gate")]

    assert set(gates) == {
        "jedi00_gate",
        "mpas00_gate",
        "obs06_gate",
        "jedi06_gate",
        "mpas06_gate",
        "obs12_gate",
        "jedi12_gate",
        "mpas12_gate",
        "obs18_gate",
        "jedi18_gate",
    }
    for name in gates:
        task = tasks[name]
        assert task["argv"][1] == "validation-gate"
        assert task["input_fingerprint"] == "sha256"
        required = task["inputs"]["required"]
        assert len(required) == 1
        assert required[0].endswith("validation.json")
