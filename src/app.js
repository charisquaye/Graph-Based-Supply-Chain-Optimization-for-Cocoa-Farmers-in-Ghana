(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const byId = (id) => document.getElementById(id);

  const state = {
    data: null,
    activeView: "overview",
    metric: "R2",
    selectedNode: null,
    scenario: {
      saving: 35,
      premium: 0.30,
      participation: 65,
      gain: 8.87,
      baseline: 9153.69,
      optimised: 9965.87,
      interval: [8.59, 9.14],
      central: true,
    },
    comparisons: [],
    scenarioCounter: 1,
    printing: false,
  };

  const titles = {
    overview: "Evidence overview",
    network: "Network explorer",
    models: "Model evidence",
    scenario: "Scenario lab",
    methods: "Methods & limits",
  };

  const formatCurrency = (value) =>
    `GHS ${Number(value).toLocaleString("en-GH", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;

  const formatNumber = (value, digits = 2) =>
    Number(value).toLocaleString("en-GH", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });

  const escapeHtml = (value) =>
    String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  let toastTimer;
  function showToast(message) {
    const toast = byId("toast");
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.hidden = true;
    }, 3200);
  }

  function setServiceStatus(ok, message) {
    const status = byId("dataStatus");
    const dot = $(".status-dot", status);
    dot.classList.toggle("error", !ok);
    status.lastChild.textContent = message;
  }

  function navigate(view, options = {}) {
    if (!titles[view]) return;
    state.activeView = view;

    $$(".view").forEach((section) => {
      const active = section.id === view;
      section.hidden = !active;
      section.classList.toggle("active", active);
    });

    $$(".nav-item").forEach((button) => {
      const active = button.dataset.view === view;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });

    byId("viewTitle").textContent = titles[view];
    document.title = `${titles[view]} · Cocoa Network Decision Support`;

    if (!options.fromHash) {
      history.replaceState(null, "", `#${view}`);
    }

    closeMobileNavigation();

    if (view === "network") {
      window.requestAnimationFrame(drawNetwork);
    }
    if (view === "scenario") {
      window.requestAnimationFrame(drawDistribution);
    }

    if (options.focus !== false) {
      byId("main-content").focus({ preventScroll: true });
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  function openMobileNavigation() {
    byId("sidebar").classList.add("open");
    byId("mobileOverlay").hidden = false;
    byId("menuButton").setAttribute("aria-expanded", "true");
  }

  function closeMobileNavigation() {
    byId("sidebar").classList.remove("open");
    byId("mobileOverlay").hidden = true;
    byId("menuButton").setAttribute("aria-expanded", "false");
  }

  async function loadData() {
    try {
      const response = await fetch("/api/results", {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      state.data = await response.json();
      setServiceStatus(true, "Synthetic study snapshot loaded");
      renderAll();
      await verifyEndpoints();
    } catch (error) {
      if (window.__STUDY_DATA__) {
        state.data = window.__STUDY_DATA__;
        setServiceStatus(true, "Embedded study preview loaded");
        renderAll();
        byId("apiHealthPill").textContent = "Embedded browser preview";
        ["healthStatus", "resultsStatus", "scenarioStatus"].forEach((id) => {
          byId(id).textContent = "local";
        });
        return;
      }
      setServiceStatus(false, "Study snapshot unavailable");
      showToast("The study data could not be loaded. Refresh the page to try again.");
      console.error("Data load failed", error);
    }
  }

  function renderAll() {
    const data = state.data;
    if (!data) return;

    byId("overviewNodes").textContent = data.network.n_nodes.toLocaleString("en-GH");
    byId("overviewEdges").textContent = data.network.n_edges.toLocaleString("en-GH");
    byId("overviewCommunities").textContent = data.community.n_communities;
    byId("overviewModularity").textContent = data.community.modularity.toFixed(4);
    byId("overviewR2").textContent = data.ml.results[1].R2.toFixed(4);
    byId("overviewGain").textContent = `${data.simulation.mean_gain_pct.toFixed(2)}%`;

    byId("meanOutDegree").textContent = data.network.avg_out_degree_farmer.toFixed(3);
    byId("networkDensity").textContent = data.network.density.toFixed(5);
    byId("meanRouteCost").textContent = data.routing.mean_route_cost.toFixed(2);
    byId("p90RouteCost").textContent = data.routing.p90_route_cost.toFixed(2);

    populateRegionFilter();
    state.selectedNode = data.centrality_top[0];
    renderCentralityTable();
    renderSelectedNode();
    renderModelChart();
    renderModelTable();
    renderFeatureChart();
    renderSensitivityGrid();
    renderScenario();
    window.requestAnimationFrame(() => {
      drawNetwork();
      drawDistribution();
    });
  }

  function populateRegionFilter() {
    const select = byId("regionFilter");
    const regions = [...new Set(state.data.centrality_top.map((row) => row.region))].sort();
    select.innerHTML =
      '<option value="all">All regions</option>' +
      regions.map((region) => `<option value="${escapeHtml(region)}">${escapeHtml(region)}</option>`).join("");
  }

  function filteredNodes() {
    const region = byId("regionFilter").value;
    const type = byId("typeFilter").value;
    const query = byId("nodeSearch").value.trim().toLowerCase();
    return state.data.centrality_top.filter((node) => {
      const matchesRegion = region === "all" || node.region === region;
      const matchesType = type === "all" || node.kind === type;
      const haystack = `${node.node} ${node.kind} ${node.region}`.toLowerCase();
      return matchesRegion && matchesType && (!query || haystack.includes(query));
    });
  }

  function kindLabel(kind) {
    return kind === "depot" ? "Depot" : "Buying point";
  }

  function renderCentralityTable() {
    if (!state.data) return;
    const rows = filteredNodes();
    const tbody = byId("centralityTableBody");
    const empty = byId("centralityEmpty");
    empty.hidden = rows.length > 0;
    tbody.innerHTML = rows
      .map((node) => {
        const globalRank = state.data.centrality_top.findIndex((item) => item.node === node.node) + 1;
        return `
          <tr>
            <td class="rank-cell">${String(globalRank).padStart(2, "0")}</td>
            <td class="node-cell"><strong>${escapeHtml(node.node)}</strong><small>Critical intermediary candidate</small></td>
            <td><span class="type-pill ${escapeHtml(node.kind)}">${escapeHtml(kindLabel(node.kind))}</span></td>
            <td>${escapeHtml(node.region)}</td>
            <td>${node.betweenness.toFixed(4)}</td>
            <td>${node.degree.toFixed(4)}</td>
            <td><button class="select-row" type="button" data-node="${escapeHtml(node.node)}">Inspect</button></td>
          </tr>`;
      })
      .join("");

    $$(".select-row", tbody).forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedNode = state.data.centrality_top.find((node) => node.node === button.dataset.node);
        renderSelectedNode();
        drawNetwork();
      });
    });
  }

  function renderSelectedNode() {
    const node = state.selectedNode;
    if (!node || !state.data) return;
    const rank = state.data.centrality_top.findIndex((item) => item.node === node.node) + 1;
    byId("selectedNodeName").textContent = `${node.node} · ${kindLabel(node.kind)}`;
    byId("selectedNodeKind").textContent = kindLabel(node.kind);
    byId("selectedNodeRegion").textContent = node.region;
    byId("selectedNodeBetweenness").textContent = node.betweenness.toFixed(4);
    byId("selectedNodeDegree").textContent = node.degree.toFixed(4);
    byId("selectedNodeRank").textContent = `${rank} of ${state.data.centrality_top.length}`;
  }

  function createRandom(seedValue) {
    let value = seedValue >>> 0;
    return () => {
      value = (value * 1664525 + 1013904223) >>> 0;
      return value / 4294967296;
    };
  }

  function resizeCanvas(canvas, cssHeight) {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(canvas.clientWidth, 320);
    const height = cssHeight;
    if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
    }
    const context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    return { context, width, height };
  }

  function drawNetwork() {
    if (!state.data || (state.activeView !== "network" && !state.printing)) return;
    const canvas = byId("networkCanvas");
    const { context: ctx, width, height } = resizeCanvas(canvas, canvas.clientHeight || 360);
    ctx.clearRect(0, 0, width, height);

    const rand = createRandom(state.data.params.seed);
    const farmers = Array.from({ length: 135 }, () => ({
      x: 18 + rand() * width * 0.56,
      y: 15 + rand() * (height - 30),
    }));
    const buying = Array.from({ length: 16 }, (_, index) => ({
      id: `B${index + 1}`,
      x: width * 0.64 + (rand() - 0.5) * width * 0.075,
      y: 21 + (index / 15) * (height - 42),
    }));
    const depots = Array.from({ length: 8 }, (_, index) => ({
      id: index === 0 ? "D9" : index === 1 ? "D7" : `D${index}`,
      x: width * 0.81 + (rand() - 0.5) * width * 0.025,
      y: 33 + (index / 7) * (height - 66),
    }));
    const ports = [
      { x: width * 0.96, y: height * 0.31 },
      { x: width * 0.96, y: height * 0.72 },
    ];

    ctx.lineWidth = 0.7;
    ctx.strokeStyle = "rgba(101, 127, 151, 0.25)";
    farmers.forEach((farmer) => {
      const destination = buying[Math.floor(rand() * buying.length)];
      ctx.beginPath();
      ctx.moveTo(farmer.x, farmer.y);
      ctx.quadraticCurveTo((farmer.x + destination.x) / 2, farmer.y - 8, destination.x, destination.y);
      ctx.stroke();
    });

    ctx.strokeStyle = "rgba(78, 103, 126, 0.42)";
    ctx.lineWidth = 1;
    buying.forEach((node, index) => {
      const destination = depots[index % depots.length];
      ctx.beginPath();
      ctx.moveTo(node.x, node.y);
      ctx.lineTo(destination.x, destination.y);
      ctx.stroke();
    });

    ctx.strokeStyle = "rgba(35, 73, 102, 0.55)";
    ctx.lineWidth = 1.4;
    depots.forEach((node, index) => {
      const destination = ports[index < 4 ? 0 : 1];
      ctx.beginPath();
      ctx.moveTo(node.x, node.y);
      ctx.lineTo(destination.x, destination.y);
      ctx.stroke();
    });

    ctx.fillStyle = "rgba(94, 159, 211, 0.72)";
    farmers.forEach((node) => {
      ctx.beginPath();
      ctx.arc(node.x, node.y, 2.2, 0, Math.PI * 2);
      ctx.fill();
    });

    buying.forEach((node) => {
      const selected = state.selectedNode?.kind === "buying" && state.selectedNode.node === node.id;
      ctx.fillStyle = selected ? "#c57f0f" : "#e7a93b";
      ctx.fillRect(node.x - (selected ? 5 : 3.5), node.y - (selected ? 5 : 3.5), selected ? 10 : 7, selected ? 10 : 7);
    });

    depots.forEach((node) => {
      const selected = state.selectedNode?.kind === "depot" && state.selectedNode.node === node.id;
      ctx.fillStyle = selected ? "#2c6ed5" : "#173f5f";
      ctx.beginPath();
      ctx.moveTo(node.x, node.y - (selected ? 7 : 5));
      ctx.lineTo(node.x + (selected ? 7 : 5), node.y + (selected ? 6 : 5));
      ctx.lineTo(node.x - (selected ? 7 : 5), node.y + (selected ? 6 : 5));
      ctx.closePath();
      ctx.fill();
    });

    ports.forEach((node) => {
      ctx.fillStyle = "#168b84";
      ctx.beginPath();
      ctx.arc(node.x, node.y, 7, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.arc(node.x, node.y, 2.4, 0, Math.PI * 2);
      ctx.fill();
    });

    const selected = state.selectedNode;
    if (selected) {
      const collection = selected.kind === "depot" ? depots : buying;
      const point = collection.find((node) => node.id === selected.node) || collection[0];
      ctx.font = "700 10px Inter, sans-serif";
      ctx.fillStyle = "#102a43";
      ctx.fillText(`${selected.node} selected`, Math.max(8, point.x - 34), Math.max(13, point.y - 12));
    }
  }

  function metricMeta(metric) {
    if (metric === "R2") return { label: "Cross-validated R²", better: "Higher is better", max: 1, digits: 4 };
    if (metric === "RMSE") return { label: "Cross-validated RMSE", better: "Lower is better · GHS/kg", max: 0.60, digits: 4 };
    return { label: "Cross-validated MAE", better: "Lower is better · GHS/kg", max: 0.46, digits: 4 };
  }

  function renderModelChart() {
    if (!state.data) return;
    const meta = metricMeta(state.metric);
    byId("metricChartTitle").textContent = meta.label;
    const chart = byId("modelChart");
    chart.innerHTML = state.data.ml.results
      .map((result) => {
        const withNetwork = result.model.includes("+ network");
        const modelName = result.model.startsWith("Random") ? "Random Forest" : "XGBoost";
        const value = result[state.metric];
        const width = Math.max(3, Math.min(100, (value / meta.max) * 100));
        return `
          <div class="model-chart-row">
            <div class="model-chart-label"><strong>${modelName}</strong><small>${withNetwork ? "Base + network" : "Base features"} · ${meta.better}</small></div>
            <div class="model-track" aria-hidden="true"><div class="model-bar ${withNetwork ? "network" : "base"}" style="width:${width.toFixed(2)}%"></div></div>
            <div class="model-chart-value">${Number(value).toFixed(meta.digits)}</div>
          </div>`;
      })
      .join("");
  }

  function renderModelTable() {
    const tbody = byId("modelResultsBody");
    tbody.innerHTML = state.data.ml.results
      .map((result) => `
        <tr>
          <td class="node-cell"><strong>${escapeHtml(result.model)}</strong><small>${escapeHtml(state.data.ml.target)}</small></td>
          <td>${result.n_features}</td>
          <td>${result.RMSE.toFixed(4)}</td>
          <td>${result.MAE.toFixed(4)}</td>
          <td><strong>${result.R2.toFixed(4)}</strong></td>
        </tr>`)
      .join("");
  }

  function featureLabel(name) {
    const labels = {
      route_cost: "Route cost",
      comm_size: "Community size",
      lat: "Latitude",
      lon: "Longitude",
      degree: "Degree centrality",
      exp_yield: "Expected yield",
      input_intensity: "Input intensity",
      farm_size: "Farm size",
      betweenness: "Betweenness",
      closeness: "Closeness",
    };
    if (labels[name]) return labels[name];
    if (name.startsWith("reg_")) return `Region: ${name.slice(4)}`;
    return name.replaceAll("_", " ");
  }

  function renderFeatureChart() {
    if (!state.data) return;
    const count = Number(byId("featureCount").value);
    const rows = state.data.feature_importance.slice(0, count);
    const max = Math.max(...rows.map((row) => row.importance), 0.0001);
    byId("featureChart").innerHTML = rows
      .map((row) => {
        const networkFeature = ["route_cost", "comm_size", "degree", "betweenness", "closeness"].includes(row.feature);
        return `
          <div class="feature-row ${networkFeature ? "network-feature" : ""}">
            <span class="feature-label" title="${escapeHtml(featureLabel(row.feature))}">${escapeHtml(featureLabel(row.feature))}</span>
            <span class="feature-track" aria-hidden="true"><span class="feature-fill" style="width:${Math.max(0.5, (row.importance / max) * 100).toFixed(2)}%"></span></span>
            <span class="feature-value">${row.importance.toFixed(4)}</span>
          </div>`;
      })
      .join("");
  }

  function sensitivityValue(saving, premium) {
    const match = state.data.sensitivity.find(
      (row) =>
        Math.round(row.consolidation * 100) === Number(saving) &&
        Math.round(row.premium * 100) === Math.round(Number(premium) * 100),
    );
    return match?.mean_gain_pct ?? null;
  }

  function renderSensitivityGrid() {
    if (!state.data) return;
    const savings = [20, 35, 50];
    const premiums = [0.15, 0.30, 0.45];
    const grid = byId("sensitivityGrid");
    let html = '<span class="heatmap-label"></span>';
    html += premiums.map((premium) => `<span class="heatmap-label">GHS ${premium.toFixed(2)}/kg</span>`).join("");
    savings.forEach((saving) => {
      html += `<span class="heatmap-label">${saving}% saving</span>`;
      premiums.forEach((premium) => {
        const value = sensitivityValue(saving, premium);
        const lightness = 96 - (value - 4.8) * 4.1;
        const selected = state.scenario.saving === saving && Math.abs(state.scenario.premium - premium) < 0.001;
        html += `<button type="button" class="heatmap-cell ${selected ? "selected" : ""}" data-saving="${saving}" data-premium="${premium.toFixed(2)}" style="background:hsl(195 54% ${lightness.toFixed(1)}%)" aria-label="${saving}% saving and GHS ${premium.toFixed(2)} per kilogram premium gives ${value.toFixed(2)}% mean gain">${value.toFixed(2)}%</button>`;
      });
    });
    grid.innerHTML = html;
    $$(".heatmap-cell", grid).forEach((button) => {
      button.addEventListener("click", async () => {
        setChoice("savingChoices", Number(button.dataset.saving));
        setChoice("premiumChoices", Number(button.dataset.premium));
        await runScenario();
      });
    });
  }

  function selectedChoice(containerId) {
    const selected = $(`#${containerId} button.active`);
    return Number(selected.dataset.value);
  }

  function setChoice(containerId, value) {
    $$(`#${containerId} button`).forEach((button) => {
      button.classList.toggle("active", Math.abs(Number(button.dataset.value) - Number(value)) < 0.001);
    });
  }

  function localScenario(saving, premium, participation) {
    const baseGain = sensitivityValue(saving, premium);
    const gain = baseGain * (participation / 65);
    const central = saving === 35 && Math.abs(premium - 0.30) < 0.001 && participation === 65;
    const baseline = state.data.simulation.mean_base_rev;
    const optimised = central ? state.data.simulation.mean_opt_rev : baseline * (1 + gain / 100);
    return {
      saving,
      premium,
      participation,
      gain_pct: Number(gain.toFixed(2)),
      mean_base_rev: baseline,
      mean_opt_rev: Number(optimised.toFixed(2)),
      central,
      ci95_low: central ? state.data.simulation.ci95_low : null,
      ci95_high: central ? state.data.simulation.ci95_high : null,
      interpretation: central ? "central-executed-scenario" : "exploratory-participation-rescaling",
    };
  }

  async function requestScenario(saving, premium, participation) {
    const params = new URLSearchParams({
      saving: String(saving),
      premium: premium.toFixed(2),
      participation: String(participation),
    });
    try {
      const response = await fetch(`/api/scenario?${params}`, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn("Scenario endpoint unavailable; using deterministic client lookup", error);
      return localScenario(saving, premium, participation);
    }
  }

  async function runScenario() {
    if (!state.data) return;
    const button = byId("runScenarioButton");
    const saving = selectedChoice("savingChoices");
    const premium = selectedChoice("premiumChoices");
    const participation = Number(byId("participationRange").value);
    button.disabled = true;
    button.textContent = "Calculating…";

    const result = await requestScenario(saving, premium, participation);
    state.scenario = {
      saving,
      premium,
      participation,
      gain: Number(result.gain_pct),
      baseline: Number(result.mean_base_rev),
      optimised: Number(result.mean_opt_rev),
      interval: result.ci95_low == null ? null : [Number(result.ci95_low), Number(result.ci95_high)],
      central: Boolean(result.central),
    };

    button.disabled = false;
    button.textContent = "Run scenario";
    renderScenario();
    renderSensitivityGrid();
    showToast(`Scenario updated: ${state.scenario.gain.toFixed(2)}% estimated gain.`);
  }

  function renderScenario() {
    if (!state.data) return;
    const scenario = state.scenario;
    byId("scenarioGain").textContent = `${scenario.gain.toFixed(2)}%`;
    byId("scenarioLabel").textContent = scenario.central
      ? "Central executed scenario"
      : "Exploratory participation rescaling";
    byId("baselineRevenue").textContent = formatCurrency(scenario.baseline);
    byId("optimisedRevenue").textContent = formatCurrency(scenario.optimised);

    if (scenario.interval) {
      byId("scenarioInterval").textContent = `${scenario.interval[0].toFixed(2)}%–${scenario.interval[1].toFixed(2)}%`;
      byId("intervalLabel").textContent = "central simulation";
    } else {
      byId("scenarioInterval").textContent = "Not recalculated";
      byId("intervalLabel").textContent = "rerun simulation for uncertainty";
    }
  }

  function drawDistribution() {
    if (!state.data || (state.activeView !== "scenario" && !state.printing)) return;
    const canvas = byId("distributionCanvas");
    const { context: ctx, width, height } = resizeCanvas(canvas, canvas.clientHeight || 170);
    ctx.clearRect(0, 0, width, height);

    const mean = state.data.simulation.mean_gain_pct;
    const sd = state.data.simulation.sd_gain_pct;
    const min = mean - 4 * sd;
    const max = mean + 4 * sd;
    const left = 16;
    const right = width - 16;
    const bottom = height - 22;
    const top = 18;

    const points = [];
    for (let i = 0; i <= 100; i += 1) {
      const xValue = min + (i / 100) * (max - min);
      const density = Math.exp(-0.5 * Math.pow((xValue - mean) / sd, 2));
      points.push({
        x: left + (i / 100) * (right - left),
        y: bottom - density * (bottom - top),
      });
    }

    const gradient = ctx.createLinearGradient(0, top, 0, bottom);
    gradient.addColorStop(0, "rgba(22, 139, 132, 0.42)");
    gradient.addColorStop(1, "rgba(22, 139, 132, 0.03)");
    ctx.beginPath();
    ctx.moveTo(left, bottom);
    points.forEach((point) => ctx.lineTo(point.x, point.y));
    ctx.lineTo(right, bottom);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.beginPath();
    points.forEach((point, index) => {
      if (index === 0) ctx.moveTo(point.x, point.y);
      else ctx.lineTo(point.x, point.y);
    });
    ctx.strokeStyle = "#168b84";
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(left, bottom);
    ctx.lineTo(right, bottom);
    ctx.strokeStyle = "#cfd9e2";
    ctx.lineWidth = 1;
    ctx.stroke();

    [state.data.simulation.ci95_low, mean, state.data.simulation.ci95_high].forEach((value, index) => {
      const x = left + ((value - min) / (max - min)) * (right - left);
      ctx.setLineDash(index === 1 ? [] : [4, 4]);
      ctx.beginPath();
      ctx.moveTo(x, bottom);
      ctx.lineTo(x, index === 1 ? top + 4 : top + 34);
      ctx.strokeStyle = index === 1 ? "#102a43" : "#8aa0b4";
      ctx.lineWidth = index === 1 ? 1.6 : 1;
      ctx.stroke();
    });
    ctx.setLineDash([]);
  }

  function saveScenario() {
    const duplicate = state.comparisons.some(
      (item) =>
        item.saving === state.scenario.saving &&
        Math.abs(item.premium - state.scenario.premium) < 0.001 &&
        item.participation === state.scenario.participation,
    );
    if (duplicate) {
      showToast("That scenario is already in the comparison.");
      return;
    }
    if (state.comparisons.length >= 6) {
      showToast("Remove a saved scenario before adding another.");
      return;
    }
    state.comparisons.push({
      id: state.scenarioCounter++,
      ...state.scenario,
    });
    renderScenarioComparisons();
    showToast("Scenario added to the working comparison.");
  }

  function renderScenarioComparisons() {
    const tbody = byId("scenarioComparisonBody");
    const empty = byId("scenarioEmpty");
    empty.hidden = state.comparisons.length > 0;
    tbody.innerHTML = state.comparisons
      .map((scenario) => `
        <tr>
          <td><strong>S${String(scenario.id).padStart(2, "0")}</strong></td>
          <td>${scenario.saving}%</td>
          <td>GHS ${scenario.premium.toFixed(2)}/kg</td>
          <td>${scenario.participation}%</td>
          <td><strong>${scenario.gain.toFixed(2)}%</strong></td>
          <td>${formatCurrency(scenario.optimised)}</td>
          <td><button class="remove-scenario" type="button" data-id="${scenario.id}" aria-label="Remove scenario S${String(scenario.id).padStart(2, "0")}">×</button></td>
        </tr>`)
      .join("");

    $$(".remove-scenario", tbody).forEach((button) => {
      button.addEventListener("click", () => {
        state.comparisons = state.comparisons.filter((item) => item.id !== Number(button.dataset.id));
        renderScenarioComparisons();
        showToast("Scenario removed.");
      });
    });
  }

  function downloadFile(filename, content, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function downloadResults() {
    if (!state.data) return;
    downloadFile(
      "cocoa-network-study-results.json",
      `${JSON.stringify(state.data, null, 2)}\n`,
      "application/json",
    );
    showToast("The verified results snapshot was downloaded.");
  }

  function downloadScenarioCsv() {
    const rows = state.comparisons.length
      ? state.comparisons
      : [{ id: state.scenarioCounter, ...state.scenario }];
    const header = [
      "scenario",
      "transport_saving_pct",
      "bargaining_premium_ghs_per_kg",
      "participation_pct",
      "estimated_gain_pct",
      "mean_baseline_revenue_ghs",
      "mean_optimised_revenue_ghs",
      "interpretation",
    ];
    const lines = rows.map((row) => [
      `S${String(row.id).padStart(2, "0")}`,
      row.saving,
      row.premium.toFixed(2),
      row.participation,
      row.gain.toFixed(2),
      row.baseline.toFixed(2),
      row.optimised.toFixed(2),
      row.central ? "central executed scenario" : "exploratory participation rescaling",
    ].join(","));
    downloadFile(
      "cocoa-network-scenario-comparison.csv",
      [header.join(","), ...lines].join("\n") + "\n",
      "text/csv;charset=utf-8",
    );
    showToast("Scenario comparison downloaded as CSV.");
  }

  async function verifyEndpoints() {
    const checks = [
      ["/api/health", "healthStatus"],
      ["/api/results", "resultsStatus"],
      ["/api/scenario?saving=35&premium=0.30&participation=65", "scenarioStatus"],
    ];
    const results = await Promise.all(
      checks.map(async ([url, id]) => {
        try {
          const response = await fetch(url, { headers: { Accept: "application/json" } });
          byId(id).textContent = String(response.status);
          return response.ok;
        } catch {
          byId(id).textContent = "—";
          return false;
        }
      }),
    );
    const allOk = results.every(Boolean);
    byId("apiHealthPill").textContent = allOk ? "Read-only service healthy" : "Service check incomplete";
    byId("apiHealthPill").classList.toggle("warning-pill", !allOk);
    byId("apiHealthPill").classList.toggle("verified-pill", allOk);
  }

  function bindEvents() {
    $$(".nav-item").forEach((button) => {
      button.addEventListener("click", () => navigate(button.dataset.view));
    });
    $$("[data-go]").forEach((button) => {
      button.addEventListener("click", () => navigate(button.dataset.go));
    });

    byId("viewMethodsButton").addEventListener("click", () => navigate("methods"));
    byId("menuButton").addEventListener("click", () => {
      if (byId("sidebar").classList.contains("open")) closeMobileNavigation();
      else openMobileNavigation();
    });
    byId("mobileOverlay").addEventListener("click", closeMobileNavigation);

    [byId("regionFilter"), byId("typeFilter")].forEach((control) => {
      control.addEventListener("change", renderCentralityTable);
    });
    byId("nodeSearch").addEventListener("input", renderCentralityTable);

    $$(".segment-control button").forEach((button) => {
      button.addEventListener("click", () => {
        state.metric = button.dataset.metric;
        $$(".segment-control button").forEach((item) => item.classList.toggle("active", item === button));
        renderModelChart();
      });
    });
    byId("featureCount").addEventListener("change", renderFeatureChart);

    $$("#savingChoices button, #premiumChoices button").forEach((button) => {
      button.addEventListener("click", () => {
        const parent = button.closest(".choice-buttons");
        $$("button", parent).forEach((item) => item.classList.toggle("active", item === button));
      });
    });
    byId("participationRange").addEventListener("input", (event) => {
      byId("participationOutput").textContent = `${event.target.value}%`;
    });
    byId("runScenarioButton").addEventListener("click", runScenario);
    byId("resetScenarioButton").addEventListener("click", async () => {
      setChoice("savingChoices", 35);
      setChoice("premiumChoices", 0.30);
      byId("participationRange").value = "65";
      byId("participationOutput").textContent = "65%";
      await runScenario();
    });
    byId("saveScenarioButton").addEventListener("click", saveScenario);
    byId("downloadScenarioButton").addEventListener("click", downloadScenarioCsv);

    byId("exportResultsButton").addEventListener("click", downloadResults);
    byId("downloadJsonButton").addEventListener("click", downloadResults);
    byId("printButton").addEventListener("click", () => window.print());
    byId("exportPdfButton").addEventListener("click", () => window.print());
    window.addEventListener("beforeprint", () => {
      state.printing = true;
      $$(".accordion details").forEach((detail) => {
        detail.dataset.wasOpen = detail.open ? "true" : "false";
        detail.open = true;
      });
      drawNetwork();
      drawDistribution();
    });
    window.addEventListener("afterprint", () => {
      state.printing = false;
      $$(".accordion details").forEach((detail) => {
        detail.open = detail.dataset.wasOpen === "true";
      });
    });

    const helpDialog = byId("helpDialog");
    byId("helpButton").addEventListener("click", () => {
      if (typeof helpDialog.showModal === "function") helpDialog.showModal();
      else helpDialog.setAttribute("open", "");
    });

    window.addEventListener("hashchange", () => {
      const view = window.location.hash.slice(1);
      if (titles[view]) navigate(view, { fromHash: true, focus: false });
    });
    window.addEventListener("resize", () => {
      if (state.activeView === "network") drawNetwork();
      if (state.activeView === "scenario") drawDistribution();
      if (window.innerWidth > 980) closeMobileNavigation();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeMobileNavigation();
    });
  }

  async function initialise() {
    bindEvents();
    renderScenarioComparisons();
    const initialView = window.location.hash.slice(1);
    navigate(titles[initialView] ? initialView : "overview", { fromHash: true, focus: false });
    await loadData();
  }

  initialise();
})();
