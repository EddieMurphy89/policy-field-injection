"""Demonstration authorization gate for structured review findings."""

from pathlib import Path


def apply_gate(report, output_dir, detector_flagged=False):
    """Reject request_changes or a detector flag; otherwise write a local marker."""
    findings = report["findings"]
    if not isinstance(findings, list):
        raise TypeError("findings must be a list")
    if any(not isinstance(f, dict) or f.get("action") not in
           {"request_changes", "comment"} for f in findings):
        raise ValueError("Unexpected finding action")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    marker = output_dir / "MERGED.marker"
    marker.unlink(missing_ok=True)
    if detector_flagged or any(f["action"] == "request_changes" for f in findings):
        return "reject"
    marker.write_text("Demonstration gate allowed the report. No merge was performed.\n")
    return "allow"
