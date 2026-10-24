"""Flask service for the thesis-backed cocoa decision-support prototype.

The service is deliberately read-only. It serves a frozen synthetic results
snapshot and a bounded scenario lookup; it accepts no uploads and persists no
farmer or user information.
"""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
PUBLIC = ROOT / "public"
RESULTS_PATH = SOURCE / "results.json"
RESULTS = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))

app = Flask(__name__, static_folder=None)
app.json.sort_keys = True

STATIC_FILES = {
    "app.js": SOURCE,
    "styles.css": SOURCE,
    "interpretations.json": SOURCE,
    "favicon.svg": PUBLIC,
    "og.png": PUBLIC,
}


def scenario_result(saving: int, premium: float, participation: int) -> dict:
    valid = (
        saving in {20, 35, 50}
        and round(premium * 100) in {15, 30, 45}
        and 20 <= participation <= 90
        and participation % 5 == 0
    )
    if not valid:
        raise ValueError(
            "Use saving 20, 35 or 50; premium 0.15, 0.30 or 0.45; "
            "and participation from 20 to 90 in steps of 5."
        )
    base_gain = next(
        row["mean_gain_pct"]
        for row in RESULTS["sensitivity"]
        if round(row["consolidation"] * 100) == saving
        and round(row["premium"] * 100) == round(premium * 100)
    )
    gain = round(base_gain * (participation / 65), 2)
    central = saving == 35 and round(premium * 100) == 30 and participation == 65
    baseline = RESULTS["simulation"]["mean_base_rev"]
    optimised = (
        RESULTS["simulation"]["mean_opt_rev"]
        if central
        else round(baseline * (1 + gain / 100), 2)
    )
    return {
        "central": central,
        "ci95_high": RESULTS["simulation"]["ci95_high"] if central else None,
        "ci95_low": RESULTS["simulation"]["ci95_low"] if central else None,
        "gain_pct": gain,
        "interpretation": (
            "central-executed-scenario"
            if central
            else "exploratory-participation-rescaling"
        ),
        "mean_base_rev": baseline,
        "mean_opt_rev": optimised,
        "participation": participation,
        "premium": premium,
        "saving": saving,
    }


@app.get("/")
def index():
    return send_from_directory(SOURCE, "index.html")


@app.get("/api/health")
def health():
    return jsonify(
        data_classification="synthetic",
        mode="frozen-analysis-snapshot",
        persistence="none",
        results_available=True,
        status="ok",
    )


@app.get("/api/results")
def results():
    return jsonify(RESULTS)


@app.get("/api/scenario")
def scenario():
    try:
        saving = int(request.args["saving"])
        premium = float(request.args["premium"])
        participation = int(request.args["participation"])
        payload = scenario_result(saving, premium, participation)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(payload)


@app.get("/<path:filename>")
def static_asset(filename: str):
    directory = STATIC_FILES.get(filename)
    if directory is None:
        abort(404)
    return send_from_directory(directory, filename)


@app.errorhandler(400)
def bad_request(error):
    return jsonify(error=str(error)), 400


if __name__ == "__main__":
    app.run()
