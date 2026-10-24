"""Compare visible numbers and text lines: live baseline vs this build.

The live baseline is current/text.json (Playwright inner_text per view at 1440px).
Pass a capture with the same keys, plus optional "_page" for the whole-page check:

    python build/diff_numbers.py build/captured-text.json
"""

from __future__ import annotations

import collections
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE_PATH = ROOT / "current" / "text.json"
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
GLYPHS = "⌂◎▥◇≡◉↗₵✓!ⓘ☰×"
VIEWS = ["overview", "network", "models", "scenario", "methods"]
# Lines that sit outside the five views on the live page (top bar, status, footer).
# "CN" is the live text mark; this build replaces it with an aria-hidden logo.
# "Export PDF" is the only new visible line.
LIVE_PAGE_EXTRAS = {
    "skip to main content",
    "ghana cocoa supply-chain analytics",
    "evidence overview",
    "synthetic study snapshot loaded",
    "guide",
    "export results",
    "graph-based supply chain optimization for cocoa farmers in ghana",
    "research prototype · emmanuel mensah quaye · msc data science",
}
ALLOWED_LIVE_ONLY = {"cn"}
ALLOWED_BUILD_ONLY = {"export pdf"}


def norm(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped in GLYPHS + "→":
            continue
        lines.append(stripped.casefold())
    return lines


def main() -> int:
    capture_path = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "build" / "captured-text.json")
    live = json.loads(LIVE_PATH.read_text(encoding="utf-8"))
    build = json.loads(capture_path.read_text(encoding="utf-8"))

    report = [
        "# Number-preservation diff: live site vs v2 dashboard",
        "",
        "Source: live https://cocoa-network-decision-support.vercel.app "
        "(Playwright inner_text per view, 1440px, captured 2026-10-24) "
        "vs this build (each view opened as its own tab).",
        "",
    ]
    all_ok = True
    total = 0
    live_run = live["_chrome"][live["_chrome"].index("Frozen study run") :]
    pairs = [(view, live[view], build[view]) for view in VIEWS]
    pairs.append(("run card (sidebar → top-bar chips)", live_run, build["_runcard"]))
    report.append(
        "| Section | Numbers on live | Numbers in build | Missing in build | Extra in build | Text lines identical |"
    )
    report.append("|---|---|---|---|---|---|")
    details: list[str] = []
    for name, left, right in pairs:
        live_numbers = collections.Counter(NUM.findall(left))
        build_numbers = collections.Counter(NUM.findall(right))
        missing = live_numbers - build_numbers
        extra = build_numbers - live_numbers
        total += sum(live_numbers.values())
        live_lines, build_lines = norm(left), norm(right)
        same = live_lines == build_lines
        if missing or extra or not same:
            all_ok = False
        report.append(
            f"| {name} | {sum(live_numbers.values())} | {sum(build_numbers.values())} | "
            f"{dict(missing) or 'none'} | {dict(extra) or 'none'} | {'yes' if same else 'NO'} |"
        )
        if not same:
            details += [f"\n## Text diff: {name}", "```"]
            details += list(
                difflib.unified_diff(live_lines, build_lines, "live", "build", lineterm="", n=0)
            )
            details += ["```"]

    report += [
        "",
        "Notes: text is compared case-insensitively because the live site uppercases "
        "kickers/table headers with CSS text-transform (source strings are identical); "
        "decorative glyph-only nodes (⌂ ◎ ▥ ◇ ≡ ◉ ↗ ₵ ✓ ! ⓘ ☰ × and standalone →) were "
        "replaced by aria-hidden Lucide SVGs; the run card moved from the sidebar to "
        "top-bar chips and is compared as its own block. The \"CN\" text brand mark was "
        "replaced by the SVG logo mark (aria-hidden on both).",
        f"Total numeric tokens checked: {total}. Result: "
        + (
            "PASS — every number and every visible text line matches the live site."
            if all_ok
            else "see differences below"
        ),
    ]

    if "_page" in build:
        live_page = set(norm(live["_chrome"] + "\n" + live["overview"])) | LIVE_PAGE_EXTRAS
        build_page = set(norm(build["_page"]))
        live_only = live_page - build_page
        build_only = build_page - live_page
        report += [
            "## Whole-page line check",
            "```",
            f"live-only: {set(sorted(live_only))}",
            f"build-only: {set(sorted(build_only))}",
            "```",
        ]
        if live_only != ALLOWED_LIVE_ONLY or build_only != ALLOWED_BUILD_ONLY:
            all_ok = False
            report.append("Whole-page check: FAIL")
            unexpected_live = live_only - ALLOWED_LIVE_ONLY
            unexpected_build = build_only - ALLOWED_BUILD_ONLY
            missing_expected_live = ALLOWED_LIVE_ONLY - live_only
            missing_expected_build = ALLOWED_BUILD_ONLY - build_only
            if unexpected_live:
                report.append(f"Unexpected live-only: {set(sorted(unexpected_live))}")
            if unexpected_build:
                report.append(f"Unexpected build-only: {set(sorted(unexpected_build))}")
            if missing_expected_live:
                report.append(f"Expected live-only missing: {set(sorted(missing_expected_live))}")
            if missing_expected_build:
                report.append(f"Expected build-only missing: {set(sorted(missing_expected_build))}")

    report += details
    text = "\n".join(report)
    print(text)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
