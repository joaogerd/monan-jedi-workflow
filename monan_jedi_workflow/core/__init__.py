"""Reusable V2 workflow foundation services.

This package contains scheduler-independent contracts shared by MONAN-JEDI
components, scientific workflows, and orchestration adapters.
"""

from .workflow_spec import StageSpec, WorkflowSpec, WorkflowSpecificationError

__all__ = ["StageSpec", "WorkflowSpec", "WorkflowSpecificationError"]
