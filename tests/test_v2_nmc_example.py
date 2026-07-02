"""Executable check for the public V2 NMC YAML example."""

from pathlib import Path

from monan_jedi_workflow.components.bmatrix.nmc_pairs.stage import NmcPairsStage
from monan_jedi_workflow.core.config import load_mapping
from monan_jedi_workflow.core.stage import RunContext


def test_nmc_yaml_example_builds_four_pair_plan() -> None:
    """The documented example must remain accepted by the current stage parser."""
    config = load_mapping(Path("examples/v2/bmatrix_nmc_pairs/case.yaml.example"))
    stage = NmcPairsStage.from_context(RunContext("bmatrix", "example", Path("/tmp/workspace"), config=config))
    assert len(stage.pairs()) == 4
