"""Build a read-only PDF of the frozen study report.

Numbers are formatted with the same fixed-decimal rules as the interface.
This module does not recompute the study.
"""

from __future__ import annotations

from fpdf import FPDF
from fpdf.fonts import FontFace

NAVY = (16, 42, 67)
BLUE = (44, 110, 213)
INK = (19, 34, 56)
MUTED = (77, 93, 115)
LINE = (198, 209, 220)
PAPER = (244, 247, 249)
WHITE = (255, 255, 255)

# Settings printed in Methods & limits. They are interface copy, not a second model run.
LOUVAIN_RESOLUTION = "1.0"
ROUTE_ALGORITHM = "Dijkstra"
CROSS_VALIDATION = "k = 5, shuffled"
RANDOM_FOREST_TREES = "400"
RANDOM_FOREST_DEPTH = "None"
XGBOOST_TREES = "500"
XGBOOST_DEPTH = "4"
LEARNING_RATE = "0.05"
TARGET_UNIT = "GHS/kg"


def fixed(value: float, digits: int) -> str:
    return f"{float(value):.{digits}f}"


def grouped(value: int) -> str:
    return f"{int(value):,}"


def ghs(value: float) -> str:
    return f"GHS {float(value):,.2f}"


def percent(value: float, digits: int = 2) -> str:
    return f"{fixed(value, digits)}%"


def feature_label(name: str) -> str:
    labels = {
        "route_cost": "Route cost",
        "comm_size": "Community size",
        "lat": "Latitude",
        "lon": "Longitude",
        "degree": "Degree centrality",
        "exp_yield": "Expected yield",
        "input_intensity": "Input intensity",
        "farm_size": "Farm size",
        "betweenness": "Betweenness",
        "closeness": "Closeness",
    }
    if name in labels:
        return labels[name]
    if name.startswith("reg_"):
        return f"Region: {name[4:]}"
    return name.replace("_", " ")


def kind_label(kind: str) -> str:
    if kind == "depot":
        return "Depot"
    if kind == "buying":
        return "Buying point"
    return kind


def sensitivity_gain(results: dict, saving: int, premium: float) -> float:
    for row in results["sensitivity"]:
        if round(row["consolidation"] * 100) == saving and round(row["premium"] * 100) == round(premium * 100):
            return row["mean_gain_pct"]
    raise KeyError(f"No sensitivity row for saving {saving} and premium {premium}")


class _Report(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.set_xy(self.l_margin, 8)
        self.cell(0, 5, "Cocoa Network Decision Support  |  Frozen study report")
        self.set_draw_color(*LINE)
        self.line(self.l_margin, 14.5, self.w - self.r_margin, 14.5)
        self.set_y(self.t_margin)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_draw_color(*LINE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(
            0,
            5,
            f"Synthetic study data. Not operational advice.    Page {self.page_no()}/{{nb}}",
            align="C",
        )


def _section(pdf: _Report, title: str) -> None:
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.ln(4)
    pdf.set_fill_color(*BLUE)
    pdf.rect(pdf.l_margin, pdf.get_y() + 1.2, 2.2, 5.2, "F")
    pdf.set_x(pdf.l_margin + 5)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _paragraph(pdf: _Report, text: str) -> None:
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 5, text)
    pdf.ln(1.5)


def _note(pdf: _Report, text: str) -> None:
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 4.4, text)
    pdf.ln(1)


def _table(pdf: _Report, rows: list[list[str]], widths: tuple[float, ...]) -> None:
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*INK)
    pdf.set_draw_color(*LINE)
    pdf.set_fill_color(*PAPER)
    heading = FontFace(emphasis="BOLD", color=WHITE, fill_color=NAVY, size_pt=8)
    with pdf.table(
        col_widths=widths,
        headings_style=heading,
        text_align="LEFT",
        line_height=4.6,
        padding=1.6,
        borders_layout="HORIZONTAL_LINES",
        cell_fill_color=PAPER,
        cell_fill_mode="EVEN_ROWS",
        repeat_headings=1,
    ) as table:
        for values in rows:
            row = table.row()
            for value in values:
                row.cell(value)
    pdf.ln(1.5)


def _metric_table(pdf: _Report, pairs: list[tuple[str, str]]) -> None:
    rows = [["Measure", "Value"], *[[label, value] for label, value in pairs]]
    _table(pdf, rows, (1.4, 1))


def build_report_pdf(results: dict) -> bytes:
    network = results["network"]
    community = results["community"]
    routing = results["routing"]
    simulation = results["simulation"]
    ml = results["ml"]
    params = results["params"]
    models = ml["results"]
    random_forest_base, random_forest_network, xgboost_base, xgboost_network = models

    pdf = _Report(format="A4", unit="mm")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(16, 20, 16)
    pdf.set_title("Cocoa Network Decision Support - frozen study report")
    pdf.set_author("Emmanuel Mensah Quaye")
    pdf.set_subject(f"Synthetic study snapshot, seed {params['seed']}")
    pdf.set_creator("Cocoa Network Decision Support")
    pdf.add_page()

    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 42, "F")
    pdf.set_xy(16, 10)
    pdf.set_text_color(143, 201, 238)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, "GRAPH-BASED SUPPLY-CHAIN OPTIMISATION", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(16)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 9, "Cocoa Network Decision Support", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(16)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, "Frozen study report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(48)

    _paragraph(
        pdf,
        "Graph-Based Supply Chain Optimization for Cocoa Farmers in Ghana. "
        "Emmanuel Mensah Quaye, MSc Data Science. "
        "This report reprints the interface figures from the frozen synthetic snapshot. "
        "It is indicative study evidence, not operational advice and not a forecast.",
    )
    _metric_table(
        pdf,
        [
            ("Random seed", str(params["seed"])),
            ("Cross-validation", "5 folds"),
            ("Simulation runs", grouped(simulation["n_iterations"])),
            ("Data", "Synthetic study snapshot"),
        ],
    )

    _section(pdf, "1. Evidence overview")
    _paragraph(
        pdf,
        "Headline evidence from the executed analysis. "
        "The same figures are shown on the Evidence overview.",
    )
    _metric_table(
        pdf,
        [
            ("Network scale", f"{grouped(network['n_nodes'])} nodes"),
            ("Directed edges", grouped(network["n_edges"])),
            ("Community structure", f"{community['n_communities']} Louvain groups"),
            ("Modularity", fixed(community["modularity"], 4)),
            ("Best predictive fit", f"Random Forest R2 {fixed(random_forest_network['R2'], 4)}"),
            ("Predictive specification", "Base + network features"),
            ("Central scenario mean revenue gain", percent(simulation["mean_gain_pct"])),
            ("Simulation sample", f"N = {grouped(simulation['n_iterations'])}"),
        ],
    )

    _section(pdf, "2. Network explorer")
    _paragraph(
        pdf,
        "Structural indicators and the critical-intermediary ranking. "
        "The default selection is the first ranked node.",
    )
    _metric_table(
        pdf,
        [
            ("Mean farmer out-degree", fixed(network["avg_out_degree_farmer"], 3)),
            ("Network density", fixed(network["density"], 5)),
            ("Mean route cost", fixed(routing["mean_route_cost"], 2)),
            ("90th percentile route cost", fixed(routing["p90_route_cost"], 2)),
            ("Reachable farmers", grouped(routing["reachable_farmers"])),
            ("Minimum route cost", fixed(routing["min_route_cost"], 2)),
            ("Median route cost", fixed(routing["median_route_cost"], 2)),
            ("Maximum route cost", fixed(routing["max_route_cost"], 2)),
        ],
    )
    first = results["centrality_top"][0]
    first_rank = 1
    _note(
        pdf,
        "Default selected intermediary: "
        f"{first['node']}, {kind_label(first['kind'])}, {first['region']}. "
        f"Weighted betweenness {fixed(first['betweenness'], 4)}. "
        f"Degree centrality {fixed(first['degree'], 4)}. "
        f"Rank {first_rank} of {len(results['centrality_top'])}.",
    )
    ranking = [["Rank", "Node", "Type", "Region", "Betweenness", "Degree"]]
    for index, node in enumerate(results["centrality_top"], start=1):
        ranking.append(
            [
                f"{index:02d}",
                node["node"],
                kind_label(node["kind"]),
                node["region"],
                fixed(node["betweenness"], 4),
                fixed(node["degree"], 4),
            ]
        )
    _table(pdf, ranking, (0.7, 0.8, 1.3, 1.5, 1.2, 1))

    _section(pdf, "3. Model evidence")
    _paragraph(
        pdf,
        f"Cross-validated performance with and without graph-derived features. "
        f"5-fold cross-validation, n = {grouped(ml['n_obs'])}. "
        "The chart opens on R2. The table lists RMSE, MAE and R2. "
        f"Target: {ml['target']}.",
    )
    r2_rows = [["Model", "Features", "R2"]]
    for result in models:
        features = "Base + network" if "+ network" in result["model"] else "Base features"
        short_name = "Random Forest" if result["model"].startswith("Random") else "XGBoost"
        r2_rows.append([short_name, features, fixed(result["R2"], 4)])
    _table(pdf, r2_rows, (1.3, 1.3, 0.8))

    forest_reduction = (random_forest_base["RMSE"] - random_forest_network["RMSE"]) / random_forest_base["RMSE"] * 100
    xgboost_reduction = (xgboost_base["RMSE"] - xgboost_network["RMSE"]) / xgboost_base["RMSE"] * 100
    _metric_table(
        pdf,
        [
            (
                "Random Forest RMSE reduction",
                f"{percent(forest_reduction)} ({fixed(random_forest_base['RMSE'], 4)} to {fixed(random_forest_network['RMSE'], 4)})",
            ),
            (
                "XGBoost RMSE reduction",
                f"{percent(xgboost_reduction)} ({fixed(xgboost_base['RMSE'], 4)} to {fixed(xgboost_network['RMSE'], 4)})",
            ),
        ],
    )
    _note(pdf, "RMSE reduction is the relative drop from the base-feature model to the base-plus-network model.")

    full_rows = [["Model", "Features", "RMSE", "MAE", "R2"]]
    for result in models:
        full_rows.append(
            [
                result["model"],
                str(result["n_features"]),
                fixed(result["RMSE"], 4),
                fixed(result["MAE"], 4),
                fixed(result["R2"], 4),
            ]
        )
    _table(pdf, full_rows, (2.4, 0.8, 0.8, 0.8, 0.8))

    importance_rows = [["Feature", "Importance"]]
    for row in results["feature_importance"]:
        importance_rows.append([feature_label(row["feature"]), fixed(row["importance"], 4)])
    _paragraph(
        pdf,
        "Feature importance for the augmented XGBoost model. "
        "The interface opens on the top 5 and can show the top 10 or all 16. "
        "This report lists all 16.",
    )
    _table(pdf, importance_rows, (1.6, 0.8))
    _metric_table(
        pdf,
        [
            ("Yield R2, base features", fixed(results["yield_check"]["R2_base"], 4)),
            ("Yield R2, base + network", fixed(results["yield_check"]["R2_base_plus_network"], 4)),
        ],
    )
    _note(
        pdf,
        "The yield check does not show a comparable improvement. "
        "Network features recover a price signal built into the synthetic generator. "
        "They are not causal proof.",
    )

    _section(pdf, "4. Scenario lab")
    _paragraph(
        pdf,
        "Central executed scenario: transport saving 35%, bargaining premium GHS 0.30/kg, "
        "participation 65%. The 3 x 3 sensitivity grid below is the executed grid. "
        "Other participation settings in the interface are an exploratory rescaling, "
        "not a second Monte Carlo run.",
    )
    _metric_table(
        pdf,
        [
            ("Estimated aggregate revenue gain", percent(simulation["mean_gain_pct"])),
            ("Mean baseline revenue", f"{ghs(simulation['mean_base_rev'])} per farmer"),
            ("Mean optimised revenue", f"{ghs(simulation['mean_opt_rev'])} per farmer"),
            (
                "95% simulation interval",
                f"{percent(simulation['ci95_low'])}-{percent(simulation['ci95_high'])}",
            ),
            ("Distribution lower 95%", percent(simulation["ci95_low"])),
            ("Distribution mean", percent(simulation["mean_gain_pct"])),
            ("Distribution upper 95%", percent(simulation["ci95_high"])),
            ("Participation assumption", "65%"),
            ("Participation range", "20% to 90%, step 5"),
        ],
    )
    savings = (20, 35, 50)
    premiums = (0.15, 0.30, 0.45)
    grid = [["Transport saving", "GHS 0.15/kg", "GHS 0.30/kg", "GHS 0.45/kg"]]
    for saving in savings:
        grid.append(
            [
                f"{saving}%",
                *[percent(sensitivity_gain(results, saving, premium)) for premium in premiums],
            ]
        )
    _paragraph(pdf, "Mean revenue gain by transport saving and bargaining premium.")
    _table(pdf, grid, (1.3, 1, 1, 1))
    _note(
        pdf,
        "The executed model caps participation probability at 90%. "
        "Assumptions do not guarantee returns. Field validation is required.",
    )

    _section(pdf, "5. Methods and limits")
    _paragraph(pdf, "Route-weight settings, predictive settings and Monte Carlo settings as shown under Methods & limits.")
    _metric_table(
        pdf,
        [
            ("Random seed", str(params["seed"])),
            ("Distance coefficient alpha", fixed(params["A"], 1)),
            ("Tariff coefficient beta", fixed(params["B"], 1)),
            ("Time coefficient gamma", fixed(params["C"], 1)),
            ("Reliability coefficient delta", fixed(params["D"], 1)),
            ("Louvain resolution", LOUVAIN_RESOLUTION),
            ("Route algorithm", ROUTE_ALGORITHM),
            ("Cross-validation", CROSS_VALIDATION),
            ("Random Forest", f"{RANDOM_FOREST_TREES} trees"),
            ("Random Forest maximum depth", RANDOM_FOREST_DEPTH),
            ("XGBoost", f"{XGBOOST_TREES} trees"),
            ("XGBoost depth", XGBOOST_DEPTH),
            ("Learning rate", LEARNING_RATE),
            ("Target", TARGET_UNIT),
            ("Iterations", f"N = {grouped(simulation['n_iterations'])}"),
            ("Central saving", f"{int(round(params['consolidation_saving'] * 100))}%"),
            ("Central premium", f"GHS {fixed(params['bargain_premium'], 2)}/kg"),
            ("Mean gain", percent(simulation["mean_gain_pct"])),
            ("Standard deviation", fixed(simulation["sd_gain_pct"], 2)),
            (
                "95% interval",
                f"{percent(simulation['ci95_low'])}-{percent(simulation['ci95_high'])}",
            ),
            (
                "Sensitivity span",
                f"{percent(min(row['mean_gain_pct'] for row in results['sensitivity']))}"
                f"-{percent(max(row['mean_gain_pct'] for row in results['sensitivity']))}",
            ),
        ],
    )
    _paragraph(
        pdf,
        f"The {percent(simulation['mean_gain_pct'])} figure is the mean of a synthetic, "
        "assumption-dependent Monte Carlo scenario. It does not predict what farmers will earn. "
        "Betweenness identifies candidates for review. It does not identify a depot that should be removed. "
        "The service is read-only: a frozen snapshot, no uploads, and no stored farmer or user data.",
    )
    _note(
        pdf,
        "Required before operational use: an observed-data partnership, external and temporal validation, "
        "human-centred research, and security and accountability controls.",
    )

    return bytes(pdf.output())
