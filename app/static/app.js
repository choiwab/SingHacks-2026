const state = {
  case: null,
  evidence: {},
  prepared: null,
  opening: null,
  followUp: null,
  rehearsalComplete: false,
  tasks: [],
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const svgNamespace = "http://www.w3.org/2000/svg";

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "The service did not respond." }));
    throw new Error(error.detail || "The service did not respond.");
  }
  return response.json();
}

function formatNumber(value, digits = 2) {
  return new Intl.NumberFormat("en-SG", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

function formatDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => {
    toast.hidden = true;
  }, 4200);
}

function setProgress(current) {
  const order = ["attention", "stress", "council", "rehearse", "act", "outcome"];
  const currentIndex = order.indexOf(current);
  $$('[data-progress]').forEach((item) => {
    const index = order.indexOf(item.dataset.progress);
    item.classList.toggle("is-complete", index < currentIndex);
    item.classList.toggle("is-current", index === currentIndex);
  });
}

function renderCase(caseData) {
  state.case = caseData;
  const client = caseData.client;
  $("#client-name").textContent = client.name;
  $("#client-id").textContent = client.id;
  $("#client-meta").textContent = `${client.booking_centre} · ${client.risk_profile} · ${client.liquidity_need} liquidity need`;
  $("#attention-copy").textContent = caseData.attention;
  $("#rm-name").textContent = client.rm_name;
  $("#kyc-due").textContent = formatDate(client.kyc_due);
  $("#property-weight").textContent = `${formatNumber(caseData.portfolio.property_weight_pct, 1)}%`;
  $("#current-ltv").textContent = `${formatNumber(caseData.facility.ltv_pct)}%`;
  $("#cash-need").textContent = formatNumber(caseData.cash_need.amount_m, 1);
}

function svgElement(tag, attributes = {}, text = null) {
  const node = document.createElementNS(svgNamespace, tag);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
  if (text !== null) node.textContent = text;
  return node;
}

function renderLtvChart(history, stressedLtv, trigger) {
  const svg = $("#ltv-chart");
  const title = $("#ltv-chart-title");
  const description = $("#ltv-chart-desc");
  svg.replaceChildren(title, description);

  const left = 54;
  const right = 680;
  const top = 24;
  const bottom = 218;
  const min = 50;
  const max = 78;
  const observedRight = 530;
  const scenarioX = 656;
  const y = (value) => bottom - ((value - min) / (max - min)) * (bottom - top);
  const observedX = history.map((_, index) => left + (index * (observedRight - left)) / (history.length - 1));
  const triggerY = y(trigger);

  svg.append(svgElement("rect", {
    x: left,
    y: top,
    width: right - left,
    height: triggerY - top,
    class: "chart-breach-zone",
  }));

  [50, 60, 70].forEach((value) => {
    const gridY = y(value);
    svg.append(svgElement("line", { x1: left, y1: gridY, x2: right, y2: gridY, class: "chart-grid" }));
    svg.append(svgElement("text", { x: 8, y: gridY + 4, class: "chart-axis-label" }, `${value}%`));
  });

  svg.append(svgElement("line", {
    x1: left,
    y1: triggerY,
    x2: right,
    y2: triggerY,
    class: "chart-trigger-line",
  }));
  svg.append(svgElement("text", {
    x: right,
    y: triggerY - 8,
    "text-anchor": "end",
    class: "chart-value-label",
  }, `${formatNumber(trigger)}% trigger`));

  const observedPoints = history.map((point, index) => `${observedX[index]},${y(point.ltv)}`).join(" ");
  svg.append(svgElement("polyline", { points: observedPoints, class: "chart-history" }));
  const last = history.at(-1);
  svg.append(svgElement("line", {
    x1: observedRight,
    y1: y(last.ltv),
    x2: scenarioX,
    y2: y(stressedLtv),
    class: "chart-scenario",
  }));

  history.forEach((point, index) => {
    const pointClass = index === history.length - 1 ? "chart-point-current" : "chart-point";
    svg.append(svgElement("circle", { cx: observedX[index], cy: y(point.ltv), r: 5, class: pointClass }));
    svg.append(svgElement("text", {
      x: observedX[index],
      y: bottom + 28,
      "text-anchor": "middle",
      class: "chart-date-label",
    }, point.label));
    if (index === 0 || index === history.length - 1) {
      svg.append(svgElement("text", {
        x: observedX[index],
        y: y(point.ltv) - 12,
        "text-anchor": "middle",
        class: "chart-value-label",
      }, `${formatNumber(point.ltv)}%`));
    }
  });

  svg.append(svgElement("circle", { cx: scenarioX, cy: y(stressedLtv), r: 7, class: "chart-point-stress" }));
  svg.append(svgElement("text", {
    x: scenarioX,
    y: bottom + 28,
    "text-anchor": "middle",
    class: "chart-date-label",
  }, "Stress"));
  svg.append(svgElement("text", {
    x: scenarioX,
    y: y(stressedLtv) - 16,
    "text-anchor": "middle",
    class: "chart-note",
  }, `${formatNumber(stressedLtv)}% · breached`));
}

function renderNetwork(scenario) {
  const container = $("#network-nodes");
  container.replaceChildren();
  const propertyHoldings = scenario.holdings.filter((holding) => holding.property_linked);
  const nodes = [
    ...propertyHoldings.map((holding) => ({
      title: holding.name,
      meta: `${holding.liquidity} · ${formatNumber(holding.portfolio_weight_pct, 1)}% weight`,
      value: `HKD ${formatNumber(holding.current_value_m, 1)}m`,
      evidence: holding.evidence_id,
    })),
    {
      title: "Lombard facility",
      meta: "Secured borrowing · 69.41% LTV",
      value: "HKD 58.0m",
      evidence: "facility:CF-0002",
    },
    {
      title: "Redevelopment contribution",
      meta: "Confirmed · due Jun 2027",
      value: "HKD 60.0m",
      evidence: "cash-need:CN-013",
    },
  ];
  nodes.forEach((item) => {
    const button = makeElement("button", "network-node");
    button.type = "button";
    button.dataset.evidence = item.evidence;
    const copy = makeElement("span");
    copy.append(makeElement("strong", null, item.title), makeElement("small", null, item.meta));
    button.append(copy, makeElement("span", null, item.value));
    container.append(button);
  });
}

function renderHoldings(holdings) {
  const body = $("#holdings-body");
  body.replaceChildren();
  holdings.forEach((holding) => {
    const row = document.createElement("tr");
    const positionCell = document.createElement("td");
    const position = makeElement("div", "position-name");
    if (holding.property_linked) position.append(makeElement("i", "property-dot"));
    const evidenceButton = makeElement("button", "table-evidence", holding.name);
    evidenceButton.type = "button";
    evidenceButton.dataset.evidence = holding.evidence_id;
    position.append(evidenceButton);
    positionCell.append(position);
    row.append(positionCell);

    const values = [
      [holding.theme, ""],
      [`HKD ${formatNumber(holding.current_value_m)}m`, "numeric"],
      [`${formatNumber(holding.portfolio_weight_pct, 1)}%`, "numeric"],
      [holding.liquidity, ""],
      [`${formatNumber(holding.advance_rate_pct, 0)}%`, "numeric"],
      [`HKD ${formatNumber(holding.stressed_value_m)}m`, "numeric"],
    ];
    values.forEach(([value, className]) => row.append(makeElement("td", className, value)));
    body.append(row);
  });
}

function renderCouncil(council) {
  const body = $("#council-body");
  body.replaceChildren();
  council.forEach((specialist) => {
    const row = document.createElement("tr");
    const role = document.createElement("td");
    role.append(makeElement("strong", null, specialist.role));
    role.append(makeElement("span", "stance", specialist.stance));
    row.append(role);
    row.append(makeElement("td", null, specialist.position));
    row.append(makeElement("td", null, specialist.concern));
    row.append(makeElement("td", null, specialist.action));
    const evidenceCell = document.createElement("td");
    const evidenceButton = makeElement("button", "evidence-count", String(specialist.evidence_ids.length));
    evidenceButton.type = "button";
    evidenceButton.dataset.evidence = specialist.evidence_ids[0];
    evidenceButton.setAttribute("aria-label", `View evidence for ${specialist.role}`);
    evidenceCell.append(evidenceButton);
    row.append(evidenceCell);
    body.append(row);
  });
}

function renderActionPlan(plan) {
  $("#brief-summary").textContent = plan.summary;
  const questions = $("#open-questions");
  questions.replaceChildren(...plan.open_questions.map((question) => makeElement("li", null, question)));
  state.tasks = plan.tasks.map((task) => ({ ...task }));
  const taskList = $("#task-list");
  taskList.replaceChildren();

  state.tasks.forEach((task, index) => {
    const row = makeElement("div", "task-row");
    row.append(makeElement("span", "task-number", String(index + 1).padStart(2, "0")));

    const titleLabel = makeElement("label", "task-title");
    titleLabel.append(makeElement("span", null, "Action"));
    const titleInput = document.createElement("input");
    titleInput.value = task.title;
    titleInput.id = `task-${index}-title`;
    titleInput.name = `task-${index}-title`;
    titleInput.setAttribute("aria-label", `Action ${index + 1}`);
    titleInput.addEventListener("input", () => {
      task.title = titleInput.value;
    });
    titleLabel.append(titleInput);

    const ownerLabel = makeElement("label", "task-owner");
    ownerLabel.append(makeElement("span", null, "Owner"));
    const ownerInput = document.createElement("input");
    ownerInput.value = task.owner;
    ownerInput.id = `task-${index}-owner`;
    ownerInput.name = `task-${index}-owner`;
    ownerInput.setAttribute("aria-label", `Owner for action ${index + 1}`);
    ownerInput.addEventListener("input", () => {
      task.owner = ownerInput.value;
    });
    ownerLabel.append(ownerInput);

    const dueLabel = makeElement("label", "task-due");
    dueLabel.append(makeElement("span", null, "Due"));
    const dueInput = document.createElement("input");
    dueInput.type = "date";
    dueInput.value = task.due;
    dueInput.id = `task-${index}-due-date`;
    dueInput.name = `task-${index}-due-date`;
    dueInput.setAttribute("aria-label", `Due date for action ${index + 1}`);
    dueInput.addEventListener("input", () => {
      task.due = dueInput.value;
    });
    dueLabel.append(dueInput);

    row.append(titleLabel, ownerLabel, dueLabel);
    taskList.append(row);
  });
}

function renderPrepared(payload) {
  state.prepared = payload;
  document.body.classList.add("is-prepared");
  state.evidence = { ...state.evidence, ...payload.evidence };
  const { scenario } = payload;
  const summary = state.case;

  $("#governance-notice").textContent = summary.governance_notice;
  $("#ltv-current-large").textContent = `${formatNumber(scenario.current.ltv_pct)}%`;
  $("#ltv-stressed-large").textContent = `${formatNumber(scenario.stressed.ltv_pct)}%`;
  $("#stressed-portfolio").textContent = `HKD ${formatNumber(scenario.stressed.portfolio_value_m)}m`;
  $("#portfolio-change").textContent = `-HKD ${formatNumber(Math.abs(scenario.stressed.portfolio_change_m))}m`;
  $("#stressed-lending").textContent = `HKD ${formatNumber(scenario.stressed.lending_value_m)}m`;
  $("#lending-change").textContent = `-HKD ${formatNumber(Math.abs(scenario.stressed.lending_change_m))}m`;
  $("#estimated-cure").textContent = `HKD ${formatNumber(scenario.stressed.cure_m)}m`;
  $("#known-cash").textContent = `HKD ${formatNumber(summary.portfolio.known_cash_m)}m`;
  $("#cash-coverage").textContent = `${formatNumber(summary.portfolio.cash_coverage_pct, 0)}% of project need`;
  renderLtvChart(summary.facility.history, scenario.stressed.ltv_pct, summary.facility.trigger_pct);
  renderNetwork(scenario);
  renderHoldings(scenario.holdings);
  renderCouncil(payload.council);
  renderActionPlan(payload.action_plan);
  $("#prepared-content").hidden = false;
  setProgress("stress");
}

async function prepareMeeting() {
  const button = $("#prepare-button");
  const note = $("#trigger-note");
  button.disabled = true;
  const buttonText = $("span", button);
  buttonText.textContent = "Building the evidence packet…";
  note.textContent = "Calculating first. Specialist perspectives follow from the same immutable evidence.";
  try {
    const payload = await request("/api/prepare", { method: "POST" });
    renderPrepared(payload);
    buttonText.textContent = "Meeting prepared";
    note.textContent = "8 holdings reconciled · 5 specialist views · every material claim linked";
    window.setTimeout(() => $("#stress-section").scrollIntoView({ behavior: "smooth", block: "start" }), 180);
  } catch (error) {
    button.disabled = false;
    buttonText.textContent = "Prepare Lau's meeting";
    note.textContent = "Preparation did not complete. Your client data was not changed.";
    showToast(`${error.message} Try preparing the meeting again.`);
  }
}

async function chooseOpening(event) {
  const button = event.target.closest("[data-opening]");
  if (!button) return;
  state.opening = button.dataset.opening;
  $$('[data-opening]').forEach((choice) => {
    choice.classList.toggle("is-selected", choice === button);
    choice.disabled = true;
  });
  try {
    const result = await request("/api/rehearse", {
      method: "POST",
      body: JSON.stringify({ opening: state.opening }),
    });
    $("#client-position").textContent = `“${result.client_position}”`;
    $("#opening-feedback").textContent = result.opening_feedback;
    $("#client-response").hidden = false;
    setProgress("rehearse");
    window.setTimeout(() => $("#client-response").scrollIntoView({ behavior: "smooth", block: "center" }), 120);
  } catch (error) {
    $$('[data-opening]').forEach((choice) => {
      choice.disabled = false;
      choice.classList.remove("is-selected");
    });
    showToast(`${error.message} Choose the opening again.`);
  }
}

async function chooseFollowUp(event) {
  const button = event.target.closest("[data-follow-up]");
  if (!button || !state.opening) return;
  state.followUp = button.dataset.followUp;
  $$('[data-follow-up]').forEach((choice) => {
    choice.classList.toggle("is-selected", choice === button);
    choice.disabled = true;
  });
  try {
    const result = await request("/api/rehearse", {
      method: "POST",
      body: JSON.stringify({ opening: state.opening, follow_up: state.followUp }),
    });
    $("#outcome-status").textContent = result.status;
    $("#outcome-headline").textContent = result.headline;
    $("#coaching-copy").textContent = result.coaching;
    $("#next-question").textContent = result.next_question;
    $("#coaching-panel").hidden = false;
    state.rehearsalComplete = true;
    updateApprovalButton();
    setProgress("act");
    window.setTimeout(() => $("#coaching-panel").scrollIntoView({ behavior: "smooth", block: "center" }), 120);
  } catch (error) {
    $$('[data-follow-up]').forEach((choice) => {
      choice.disabled = false;
      choice.classList.remove("is-selected");
    });
    showToast(`${error.message} Choose the follow-up again.`);
  }
}

function updateApprovalButton() {
  const acknowledged = $("#approval-checkbox").checked;
  $("#approve-button").disabled = !(acknowledged && state.rehearsalComplete);
}

function readablePayload(payload) {
  return Object.entries(payload)
    .map(([key, value]) => {
      const label = key.replaceAll("_", " ");
      const rendered = Array.isArray(value) ? value.join(" · ") : value;
      return `${label}: ${rendered}`;
    })
    .join(" | ");
}

function renderOutcome(payload) {
  const outcome = payload.outcome;
  const values = [
    ["Client goal", outcome.client_goal],
    ["Risk obligation", outcome.risk_obligation],
    ["Relationship stage", outcome.relationship_stage],
    ["Records prepared", outcome.records],
  ];
  const strip = $("#outcome-strip");
  strip.replaceChildren();
  values.forEach(([label, value]) => {
    const item = makeElement("div", "outcome-item");
    item.append(makeElement("span", null, label), makeElement("strong", null, value));
    strip.append(item);
  });

  const list = $("#connector-list");
  list.replaceChildren();
  payload.connectors.forEach((connector) => {
    const row = makeElement("article", "connector-row");
    row.append(makeElement("div", "connector-name", connector.name));
    const destination = makeElement("div", "connector-destination");
    destination.append(makeElement("span", null, "Destination"), makeElement("p", null, connector.destination));
    const connectorPayload = makeElement("div", "connector-payload");
    connectorPayload.append(makeElement("span", null, "Prepared payload"), makeElement("p", null, readablePayload(connector.payload)));
    row.append(destination, connectorPayload, makeElement("span", "connector-mode", connector.mode));
    list.append(row);
  });
  $("#outcome-section").hidden = false;
  setProgress("outcome");
  window.setTimeout(() => $("#outcome-section").scrollIntoView({ behavior: "smooth", block: "start" }), 120);
}

async function approvePlan() {
  const button = $("#approve-button");
  button.disabled = true;
  button.textContent = "Preparing action previews…";
  try {
    const payload = await request("/api/action-plan/approve", {
      method: "POST",
      body: JSON.stringify({
        acknowledged: $("#approval-checkbox").checked,
        tasks: state.tasks.map(({ id, title, owner, due, system }) => ({ id, title, owner, due, system })),
      }),
    });
    renderOutcome(payload);
    button.textContent = "Plan approved for preview";
    showToast("Action previews are ready. Nothing was sent or written externally.");
  } catch (error) {
    button.textContent = "Approve plan and preview actions";
    updateApprovalButton();
    showToast(`${error.message} Review the plan and try again.`);
  }
}

function openEvidence(evidenceId) {
  const evidence = state.evidence[evidenceId];
  if (!evidence) {
    showToast("This evidence record is not available in the current packet.");
    return;
  }
  $("#evidence-type").textContent = evidence.type;
  $("#evidence-title").textContent = evidence.title;
  $("#evidence-detail").textContent = evidence.detail;
  $("#evidence-source").textContent = evidence.source;
  $("#evidence-record").textContent = evidence.record;
  $("#evidence-date").textContent = formatDate(evidence.as_of);
  const formulaRow = $("#evidence-formula-row");
  formulaRow.hidden = !evidence.formula;
  $("#evidence-formula").textContent = evidence.formula || "";
  $("#evidence-dialog").showModal();
}

function bindEvents() {
  $("#prepare-button").addEventListener("click", prepareMeeting);
  $("#opening-choices").addEventListener("click", chooseOpening);
  $("#follow-up-choices").addEventListener("click", chooseFollowUp);
  $("#approval-checkbox").addEventListener("change", updateApprovalButton);
  $("#approve-button").addEventListener("click", approvePlan);
  $("#close-evidence").addEventListener("click", () => $("#evidence-dialog").close());
  $("#evidence-dialog").addEventListener("click", (event) => {
    if (event.target === $("#evidence-dialog")) $("#evidence-dialog").close();
  });
  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-evidence]");
    if (trigger) openEvidence(trigger.dataset.evidence);
  });
}

async function initialize() {
  bindEvents();
  try {
    const payload = await request("/api/case");
    state.evidence = payload.evidence;
    renderCase(payload.case);
  } catch (error) {
    showToast(`${error.message} Static case details remain available.`);
  }
}

initialize();
