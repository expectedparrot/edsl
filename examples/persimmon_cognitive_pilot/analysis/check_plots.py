#!/usr/bin/env python3
"""
check_plots.py — Visual QA checker for report plots.

Scans writeup/plots/*.png and reports issues:
  - Low DPI
  - Images too small or unusually large
  - Very light or nearly-blank images (missing content)
  - Text annotations clipped at image edges (heuristic via near-white edges)
  - Files not referenced in writeup/report.md

USAGE
-----
Run from the study root:

    python analysis/check_plots.py

Or from anywhere:

    python analysis/check_plots.py --study-root /path/to/study

Exit codes:
  0  — no issues found
  1  — one or more issues found (see output)

NOTES
-----
This script does NOT require matplotlib or EDSL.
It only needs Pillow (PIL) which is already a dependency of matplotlib.

Install if missing:  pip install Pillow
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("ERROR: Pillow and numpy are required.  Run: pip install Pillow numpy")
    sys.exit(2)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
MIN_DPI = 120          # below this → warn (target is 150)
GOOD_DPI = 150         # at or above → pass
MIN_WIDTH_PX = 600     # below → probably too small for a report
MIN_HEIGHT_PX = 300
MAX_WIDTH_PX = 6000    # above → unreasonably large (memory / render issue)
MAX_HEIGHT_PX = 6000
EDGE_BAND_PX = 8       # pixels to check for near-white edge clipping
CLIP_WHITE_THRESHOLD = 245   # pixel value considered "white"
BLANK_MEAN_THRESHOLD = 250   # if mean pixel > this, image is nearly blank
# Note: line charts with sparse data on white backgrounds legitimately have
# mean pixel values in the 245-249 range. 250 still catches truly blank PNGs.
MIN_DARK_FRACTION = 0.01     # at least 1% of pixels should be non-white


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
@dataclass
class PlotIssue:
    file: str
    severity: str          # "error" | "warning" | "info"
    check: str
    message: str


@dataclass
class PlotReport:
    file: str
    width_px: int
    height_px: int
    reported_dpi: float | None
    issues: list[PlotIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_dpi(img: Image.Image, path: Path) -> list[PlotIssue]:
    issues = []
    dpi_info = img.info.get("dpi")
    if dpi_info is None:
        issues.append(PlotIssue(
            file=path.name, severity="warning", check="dpi",
            message="No DPI metadata found in PNG. Save with dpi=150 and bbox_inches='tight'.",
        ))
    else:
        dpi = min(dpi_info)  # use the smaller of x/y dpi
        if dpi < MIN_DPI:
            issues.append(PlotIssue(
                file=path.name, severity="error", check="dpi",
                message=f"DPI is {dpi:.0f} — below minimum {MIN_DPI}. Regenerate with dpi=150.",
            ))
        elif dpi < GOOD_DPI:
            issues.append(PlotIssue(
                file=path.name, severity="warning", check="dpi",
                message=f"DPI is {dpi:.0f} — acceptable but target is {GOOD_DPI}.",
            ))
    return issues


def check_dimensions(img: Image.Image, path: Path) -> list[PlotIssue]:
    issues = []
    w, h = img.size
    if w < MIN_WIDTH_PX or h < MIN_HEIGHT_PX:
        issues.append(PlotIssue(
            file=path.name, severity="error", check="dimensions",
            message=f"Image is {w}x{h}px — too small. Increase figsize or DPI.",
        ))
    if w > MAX_WIDTH_PX or h > MAX_HEIGHT_PX:
        issues.append(PlotIssue(
            file=path.name, severity="warning", check="dimensions",
            message=f"Image is {w}x{h}px — unusually large. Check figsize.",
        ))
    return issues


def check_blank(img: Image.Image, path: Path) -> list[PlotIssue]:
    """Detect nearly-blank or all-white images."""
    issues = []
    arr = np.array(img.convert("L"), dtype=float)  # greyscale
    mean_val = arr.mean()
    dark_fraction = (arr < 200).sum() / arr.size
    if mean_val > BLANK_MEAN_THRESHOLD:
        issues.append(PlotIssue(
            file=path.name, severity="error", check="blank",
            message=f"Image appears nearly blank (mean pixel={mean_val:.0f}). "
                    "Plot may have failed to render content.",
        ))
    elif dark_fraction < MIN_DARK_FRACTION:
        issues.append(PlotIssue(
            file=path.name, severity="warning", check="blank",
            message=f"Only {dark_fraction*100:.1f}% of pixels are non-white. "
                    "Check that data was actually plotted.",
        ))
    return issues


def check_edge_clipping(img: Image.Image, path: Path) -> list[PlotIssue]:
    """
    Heuristic: if the very edge rows/columns are NOT white, content may be clipped.
    We expect tight_layout + bbox_inches='tight' to leave white borders.
    If edges are dark, something is probably cut off.
    """
    issues = []
    arr = np.array(img.convert("L"), dtype=float)
    h, w = arr.shape

    def edge_has_dark(strip: np.ndarray) -> bool:
        return bool((strip < CLIP_WHITE_THRESHOLD).any())

    # Check all four edges
    clipped_edges = []
    if edge_has_dark(arr[:EDGE_BAND_PX, :]):
        clipped_edges.append("top")
    if edge_has_dark(arr[-EDGE_BAND_PX:, :]):
        clipped_edges.append("bottom")
    if edge_has_dark(arr[:, :EDGE_BAND_PX]):
        clipped_edges.append("left")
    if edge_has_dark(arr[:, -EDGE_BAND_PX:]):
        clipped_edges.append("right")

    if clipped_edges:
        issues.append(PlotIssue(
            file=path.name, severity="warning", check="clipping",
            message=f"Non-white pixels at image edges ({', '.join(clipped_edges)}). "
                    "Labels or titles may be clipped. Use bbox_inches='tight' and check margins.",
        ))
    return issues


def check_aspect_ratio(img: Image.Image, path: Path) -> list[PlotIssue]:
    """Flag extreme aspect ratios that often indicate layout errors."""
    issues = []
    w, h = img.size
    ratio = w / h
    if ratio > 8:
        issues.append(PlotIssue(
            file=path.name, severity="warning", check="aspect_ratio",
            message=f"Very wide aspect ratio ({ratio:.1f}:1). "
                    "Check figsize — content may be squished vertically.",
        ))
    if ratio < 0.3:
        issues.append(PlotIssue(
            file=path.name, severity="warning", check="aspect_ratio",
            message=f"Very tall aspect ratio ({ratio:.2f}:1). "
                    "Check figsize — content may be squished horizontally.",
        ))
    return issues


# ---------------------------------------------------------------------------
# Report.md reference check
# ---------------------------------------------------------------------------

def get_referenced_plots(report_md: Path) -> set[str]:
    """Return set of plot filenames referenced in report.md."""
    if not report_md.exists():
        return set()
    text = report_md.read_text(encoding="utf-8")
    # Match markdown image syntax: ![...](plots/filename.png) or (writeup/plots/...)
    pattern = re.compile(r'!\[.*?\]\([^)]*?([^/)\s]+\.(?:png|jpg|jpeg|svg))[^)]*?\)', re.IGNORECASE)
    return {m.group(1) for m in pattern.finditer(text)}


def check_references(plots_dir: Path, report_md: Path) -> list[PlotIssue]:
    """Check for plots not referenced in report.md and vice versa."""
    issues = []
    existing = {p.name for p in plots_dir.glob("*.png")}
    referenced = get_referenced_plots(report_md)

    for name in sorted(existing - referenced):
        issues.append(PlotIssue(
            file=name, severity="warning", check="unreferenced",
            message=f"Plot exists in writeup/plots/ but is not referenced in report.md.",
        ))
    for name in sorted(referenced - existing):
        issues.append(PlotIssue(
            file=name, severity="error", check="missing_file",
            message=f"Plot referenced in report.md does not exist in writeup/plots/.",
        ))
    return issues


# ---------------------------------------------------------------------------
# Caption check
# ---------------------------------------------------------------------------

def check_captions(report_md: Path) -> list[PlotIssue]:
    """
    Each image reference should be followed within 3 lines by a caption
    (a line starting with 'Figure', '*Figure', or '_Figure').
    """
    issues = []
    if not report_md.exists():
        return issues

    lines = report_md.read_text(encoding="utf-8").splitlines()
    img_pattern = re.compile(r'!\[.*?\]\(.*?\)')
    caption_pattern = re.compile(r'^\s*[\*_]?\s*Figure\s+\d+', re.IGNORECASE)

    for i, line in enumerate(lines):
        if img_pattern.search(line):
            # Look for caption in next 3 lines
            snippet = lines[i+1:i+4]
            has_caption = any(caption_pattern.search(l) for l in snippet)
            if not has_caption:
                # Extract filename for the message
                m = re.search(r'!\[.*?\]\([^)]*?([^/)\s]+\.(?:png|jpg|jpeg|svg))[^)]*?\)', line)
                fname = m.group(1) if m else "(unknown)"
                issues.append(PlotIssue(
                    file=fname, severity="warning", check="caption",
                    message="Image in report.md has no 'Figure N:' caption in the following 3 lines.",
                ))
    return issues


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_checks(study_root: Path) -> list[PlotReport]:
    plots_dir = study_root / "writeup" / "plots"
    report_md = study_root / "writeup" / "report.md"

    reports: list[PlotReport] = []
    reference_issues = check_references(plots_dir, report_md)
    caption_issues   = check_captions(report_md)

    # Per-file checks
    png_files = sorted(plots_dir.glob("*.png")) if plots_dir.exists() else []

    for png in png_files:
        try:
            img = Image.open(png)
        except Exception as e:
            reports.append(PlotReport(
                file=png.name, width_px=0, height_px=0, reported_dpi=None,
                issues=[PlotIssue(
                    file=png.name, severity="error", check="open",
                    message=f"Could not open image: {e}",
                )],
            ))
            continue

        dpi_info = img.info.get("dpi")
        reported_dpi = min(dpi_info) if dpi_info else None
        w, h = img.size

        pr = PlotReport(file=png.name, width_px=w, height_px=h, reported_dpi=reported_dpi)
        pr.issues += check_dpi(img, png)
        pr.issues += check_dimensions(img, png)
        pr.issues += check_blank(img, png)
        pr.issues += check_edge_clipping(img, png)
        pr.issues += check_aspect_ratio(img, png)

        # Attach caption issues for this file
        pr.issues += [ci for ci in caption_issues if ci.file == png.name]

        reports.append(pr)

    # Add reference issues as a pseudo-report
    if reference_issues:
        pseudo = PlotReport(
            file="(report.md references)",
            width_px=0, height_px=0, reported_dpi=None,
            issues=reference_issues,
        )
        reports.append(pseudo)

    return reports


def print_report(reports: list[PlotReport]) -> int:
    """Print human-readable summary.  Returns exit code (0=ok, 1=issues)."""
    errors = 0
    warnings = 0

    for pr in reports:
        if not pr.issues:
            print(f"  OK  {pr.file}  ({pr.width_px}x{pr.height_px}px, {pr.reported_dpi or '?'}dpi)")
            continue
        print(f"\n  {pr.file}  ({pr.width_px}x{pr.height_px}px, {pr.reported_dpi or '?'}dpi)")
        for issue in pr.issues:
            marker = "ERROR  " if issue.severity == "error" else "WARN   "
            print(f"    {marker}[{issue.check}] {issue.message}")
            if issue.severity == "error":
                errors += 1
            else:
                warnings += 1

    print()
    print(f"Result: {errors} error(s), {warnings} warning(s) across {len(reports)} plot(s).")
    return 1 if errors > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Visual QA checker for report plots.")
    parser.add_argument(
        "--study-root",
        type=Path,
        default=Path.cwd(),
        help="Path to study root directory (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of human-readable text",
    )
    args = parser.parse_args()

    study_root = args.study_root.resolve()
    plots_dir = study_root / "writeup" / "plots"

    if not plots_dir.exists():
        print(f"No writeup/plots/ directory found at {study_root}")
        sys.exit(0)

    print(f"Checking plots in: {plots_dir}\n")
    reports = run_checks(study_root)

    if args.json:
        print(json.dumps([asdict(r) for r in reports], indent=2))
        has_errors = any(
            i.severity == "error"
            for r in reports
            for i in r.issues
        )
        sys.exit(1 if has_errors else 0)
    else:
        sys.exit(print_report(reports))


if __name__ == "__main__":
    main()
