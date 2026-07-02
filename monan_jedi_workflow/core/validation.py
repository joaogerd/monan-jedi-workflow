"""Structured validation results shared by V2 stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidationSeverity(str, Enum):
    """Severity assigned to one validation finding."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ValidationIssue:
    """Describe one validation finding.

    Parameters
    ----------
    code : str
        Stable machine-readable identifier for the finding.
    message : str
        Human-readable English explanation.
    severity : ValidationSeverity
        Error, warning, or informational severity.
    path : str | None, default=None
        Optional affected file or configuration path.
    """

    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    path: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Return a JSON-serializable representation of the finding."""
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "path": self.path,
        }


class ValidationError(RuntimeError):
    """Raised when a validation report contains one or more errors."""


@dataclass
class ValidationReport:
    """Collect validation findings for one operation.

    Parameters
    ----------
    subject : str
        Name of the checked entity, such as an artifact or stage.
    issues : list[ValidationIssue], default=[]
        Findings recorded during validation.
    """

    subject: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return whether the report has no error-severity findings."""
        return all(issue.severity is not ValidationSeverity.ERROR for issue in self.issues)

    def add(
        self,
        code: str,
        message: str,
        *,
        severity: ValidationSeverity = ValidationSeverity.ERROR,
        path: str | None = None,
    ) -> None:
        """Append one validation finding.

        Parameters
        ----------
        code : str
            Stable machine-readable identifier.
        message : str
            Human-readable English explanation.
        severity : ValidationSeverity, default=ValidationSeverity.ERROR
            Severity assigned to the finding.
        path : str | None, default=None
            Optional affected path.
        """
        self.issues.append(ValidationIssue(code, message, severity, path))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the report.

        Returns
        -------
        dict[str, Any]
            Subject, validity flag, and structured validation findings.
        """
        return {
            "subject": self.subject,
            "is_valid": self.is_valid,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def require_valid(self) -> None:
        """Raise when the report contains validation errors.

        Raises
        ------
        ValidationError
            Raised with all error messages in deterministic insertion order.
        """
        if self.is_valid:
            return
        messages = [issue.message for issue in self.issues if issue.severity is ValidationSeverity.ERROR]
        raise ValidationError(f"Validation failed for {self.subject}: " + "; ".join(messages))
