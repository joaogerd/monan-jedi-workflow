"""MPAS V2 documentation checks."""

from pathlib import Path


def test_mpas_tool_page_has_required_sections() -> None:
    """The MPAS tool page must include the standard user-facing sections."""
    page = Path("docs/tools/model/mpas-forecast.md").read_text(encoding="utf-8")
    required = ("## Purpose", "## Inputs", "## Outputs", "## Artifact Contract", "## Parameters", "## Dependencies", "## CLI Usage", "## Validation", "## Limitations", "## FAQ", "## References")
    assert all(section in page for section in required)
