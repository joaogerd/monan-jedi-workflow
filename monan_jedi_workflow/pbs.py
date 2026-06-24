"""Backward-compatible aliases for the MONAN-JEDI PBS scheduler API."""

from .scheduler import PBSError, Submission, load_submission, manifest_path, query, rendered_pbs_path, submit, wait

__all__ = ["PBSError", "Submission", "load_submission", "manifest_path", "query", "rendered_pbs_path", "submit", "wait"]
