"""NMC forecast-pair contracts for background-error covariance workflows."""

from .manifest import BflowManifest, BflowManifestEntry, read_bflow_manifest, write_bflow_manifest
from .model import NmcForecast, NmcPair, NmcPairError, normalize_time, plan_pairs
from .validation import validate_pairs

__all__ = [
    "BflowManifest",
    "BflowManifestEntry",
    "NmcForecast",
    "NmcPair",
    "NmcPairError",
    "normalize_time",
    "plan_pairs",
    "read_bflow_manifest",
    "validate_pairs",
    "write_bflow_manifest",
]
