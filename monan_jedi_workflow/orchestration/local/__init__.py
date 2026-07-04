"""Local execution adapters for V2 workflow specifications."""

from .runner import LocalWorkflowRunner
from .task_runner import StageTaskRunner

__all__ = ["LocalWorkflowRunner", "StageTaskRunner"]
