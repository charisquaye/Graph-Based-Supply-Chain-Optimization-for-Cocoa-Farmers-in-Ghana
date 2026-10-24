"""PDF export keeps the frozen study figures and does not rewrite them."""

from __future__ import annotations

import hashlib
import io
import json
import unittest
from pathlib import Path

from pypdf import PdfReader

from server.app import ROOT, app
from server.report_pdf import build_report_pdf

KEY_FIGURES = (
    "20250115",
    "957",
    "1,853",
    "0.7717",
    "0.8549",
    "8.87%",
    "5,000",
    "1.948",
    "0.00203",
    "322.22",
    "452.25",
    "900",
    "128.10",
    "308.10",
    "648.80",
    "0.0004",
    "0.0167",
    "0.0785",
    "0.6865",
    "0.6724",
    "0.8375",
    "31.95%",
    "29.57%",
    "0.5436",
    "0.3699",
    "0.5557",
    "0.3914",
    "0.4083",
    "0.4190",
    "0.2957",
    "0.3113",
    "0.7026",
    "0.0764",
    "0.0569",
    "0.0311",
    "0.0164",
    "0.0159",
    "0.0000",
    "0.4870",
    "0.4769",
    "9,153.69",
    "9,965.87",
    "8.59%",
    "9.14%",
    "4.88%",
    "6.24%",
    "7.60%",
    "7.51%",
    "10.24%",
    "10.15%",
    "11.50%",
    "12.86%",
    "1.0",
    "0.8",
    "0.6",
    "25.0",
    "0.05",
    "0.14",
    "400",
    "500",
    "65%",
    "90%",
)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReportPdfTests(unittest.TestCase):
    def test_export_control_is_present_and_methods_anchor_remains(self) -> None:
        html = (ROOT / "src" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="exportPdfButton" href="/api/report.pdf"', html)
        self.assertIn('id="methods"', html)
        self.assertIn('href="#main-content"', html)

    def test_pdf_opens_and_contains_the_interface_figures(self) -> None:
        client = app.test_client()
        response = client.get("/api/report.pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn(
            'attachment; filename="cocoa-network-decision-support-report.pdf"',
            response.headers["Content-Disposition"],
        )
        payload = response.data
        self.assertTrue(payload.startswith(b"%PDF"))
        reader = PdfReader(io.BytesIO(payload))
        self.assertGreaterEqual(len(reader.pages), 2)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        for figure in KEY_FIGURES:
            self.assertIn(figure, text, figure)

    def test_builder_opens_and_leaves_snapshots_untouched(self) -> None:
        watched = (
            ROOT / "src" / "results.json",
            ROOT / "results.json",
            ROOT / "tuned_results.json",
        )
        before = {path: _file_sha256(path) for path in watched}
        snapshot = json.loads((ROOT / "src" / "results.json").read_text(encoding="utf-8"))
        direct = build_report_pdf(snapshot)
        reader = PdfReader(io.BytesIO(direct))
        self.assertGreaterEqual(len(reader.pages), 2)
        after = {path: _file_sha256(path) for path in watched}
        self.assertEqual(before, after)

    def test_central_scenario_lookup_is_unchanged(self) -> None:
        response = app.test_client().get("/api/scenario?saving=35&premium=0.30&participation=65")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["gain_pct"], 8.87)
        self.assertEqual(body["mean_base_rev"], 9153.69)
        self.assertEqual(body["mean_opt_rev"], 9965.87)
        self.assertEqual(body["ci95_low"], 8.59)
        self.assertEqual(body["ci95_high"], 9.14)
        self.assertTrue(body["central"])

    def test_exploratory_rescaling_is_unchanged(self) -> None:
        response = app.test_client().get("/api/scenario?saving=20&premium=0.15&participation=65")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["gain_pct"], 4.88)
        self.assertEqual(body["mean_base_rev"], 9153.69)
        self.assertEqual(body["mean_opt_rev"], 9600.39)
        self.assertFalse(body["central"])
        self.assertIsNone(body["ci95_low"])
        self.assertIsNone(body["ci95_high"])


if __name__ == "__main__":
    unittest.main()
