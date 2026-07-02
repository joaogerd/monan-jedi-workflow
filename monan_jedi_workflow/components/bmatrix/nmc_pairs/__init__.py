"""NMC forecast-pair contracts for background-error covariance workflows."""

from .config import NmcPairsConfigurationError, NmcPairsSettings
from .manifest import BflowManifest, BflowManifestEntry, read_bflow_manifest, write_bflow_manifest
from .model import NmcForecast, NmcPair, NmcPairError, normalize_time, plan_pairs
from .stage import NmcPairsStage
from .validation import validate_bflow_manifest, validate_pairs

__all__ = [
    "BflowManifest",
    "BflowManifestEntry",
    "NmcForecast",
    "NmcPair",
    "NmcPairError",
    "NmcPairsConfigurationError",
    "NmcPairsSettings",
    "NmcPairsStage",
    "normalize_time",
    "plan_pairs",
    "read_bflow_manifest",
    "validate_bflow_manifest",
    "validate_pairs",
    "write_bflow_manifest",
]
