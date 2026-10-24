"""Export PDF uses the browser print dialog and leaves study figures untouched."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from server.app import ROOT, app


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReportPdfTests(unittest.TestCase):
    def test_export_uses_window_print_and_print_css(self) -> None:
        html = (ROOT / "src" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "src" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertIn('id="exportPdfButton"', html)
        self.assertIn('id="methods"', html)
        self.assertNotIn("/api/report.pdf", html)
        self.assertNotIn("html2pdf", html.lower())
        self.assertNotIn("html2canvas", html.lower())
        self.assertIn(
            'byId("exportPdfButton").addEventListener("click", () => window.print());',
            script,
        )
        self.assertNotIn("html2pdf", script.lower())
        self.assertIn("@media print", styles)
        self.assertIn("@page", styles)
        self.assertIn(".view[hidden]", styles)

        response = app.test_client().get("/api/report.pdf")
        self.assertEqual(response.status_code, 404)

    def test_snapshot_files_are_untouched_by_import(self) -> None:
        watched = (
            ROOT / "src" / "results.json",
            ROOT / "results.json",
            ROOT / "tuned_results.json",
        )
        before = {path: _file_sha256(path) for path in watched}
        self.assertEqual(app.test_client().get("/api/results").status_code, 200)
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

    def test_grid_cell_lookup_is_unchanged(self) -> None:
        response = app.test_client().get("/api/scenario?saving=20&premium=0.15&participation=65")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["gain_pct"], 4.88)
        self.assertEqual(body["mean_base_rev"], 9153.69)
        self.assertEqual(body["mean_opt_rev"], 9600.39)
        self.assertFalse(body["central"])
        self.assertIsNone(body["ci95_low"])
        self.assertIsNone(body["ci95_high"])


class ScenarioLabelTests(unittest.TestCase):
    """'Exploratory participation rescaling' appears only when participation is not 65%."""

    def _interpretation(self, saving: int, premium: str, participation: int) -> str:
        response = app.test_client().get(
            f"/api/scenario?saving={saving}&premium={premium}&participation={participation}"
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()["interpretation"]

    def test_every_grid_cell_at_65_is_executed_not_rescaled(self) -> None:
        for saving in (20, 35, 50):
            for premium in ("0.15", "0.30", "0.45"):
                with self.subTest(saving=saving, premium=premium):
                    expected = (
                        "central-executed-scenario"
                        if (saving, premium) == (35, "0.30")
                        else "executed-sensitivity-grid-cell"
                    )
                    self.assertEqual(self._interpretation(saving, premium, 65), expected)

    def test_participation_other_than_65_is_exploratory_rescaling(self) -> None:
        for participation in (20, 60, 70, 90):
            for saving, premium in ((35, "0.30"), (50, "0.45")):
                with self.subTest(participation=participation, saving=saving):
                    self.assertEqual(
                        self._interpretation(saving, premium, participation),
                        "exploratory-participation-rescaling",
                    )

    def test_client_fallback_uses_the_same_rule(self) -> None:
        script = (ROOT / "src" / "app.js").read_text(encoding="utf-8")
        self.assertIn('if (Number(participation) === 65) return "executed-sensitivity-grid-cell";', script)
        self.assertIn('"executed-sensitivity-grid-cell": "Executed sensitivity grid cell (800 runs)"', script)


class FeatureImportanceSourceTests(unittest.TestCase):
    def test_site_uses_tuned_results_values(self) -> None:
        import json

        site = json.loads((ROOT / "src" / "results.json").read_text(encoding="utf-8"))
        tuned = json.loads((ROOT / "tuned_results.json").read_text(encoding="utf-8"))["xgboost"]
        self.assertEqual(site["feature_importance"], tuned["feature_importance"])
        for key in ("base", "net", "cv_best_rmse", "best_params"):
            self.assertEqual(site["ml_tuned"]["xgboost"][key], tuned[key])
        html = (ROOT / "src" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Source: tuned_results.json (thesis Table 4.4)", html)


if __name__ == "__main__":
    unittest.main()
