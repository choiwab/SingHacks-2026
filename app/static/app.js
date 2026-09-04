const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];

const state = {
  data: null,
  clientId: null,
  scenario: "reopens",
  editing: false,
  lastFocus: null,
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "The server did not answer.");
  }
  return response.json();
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function setCitations(node, citations) {
  node.dataset.citations = JSON.stringify(citations || []);
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.hidden = true;
  }, 3200);
}

function renderList() {
  const list = $("#client-list");
  list.replaceChildren();
  state.data.ranking.forEach((client, index) => {
    const row = element("button", `client-row urgency-${client.urgency}`);
    row.type = "button";
    row.dataset.client = client.client_id;

    const rank = element("span", "rank");
    rank.append(element("span", "urgency-dot"), document.createTextNode(String(index + 1).padStart(2, "0")));

    const summary = element("span");
    summary.append(element("span", "client-name", client.name));
    summary.append(element("span", "client-reason", client.reason));

    const meeting = element("span", "meeting");
    if (client.meeting) {
      meeting.append(element("strong", null, client.meeting));
      meeting.append(document.createTextNode(client.meeting_source));
    } else {
      meeting.textContent = "No meeting";
    }

    row.append(rank, summary, meeting, element("span", "priority-score", client.score));
    list.append(row);
  });
  const first = state.data.ranking[0];
  const parts = first.components;
  $("#formula-example").textContent =
    `${first.name}: ${parts.gap} × ${parts.deadline} × ${parts.consequence} → ${first.score}`;
}

function renderCitedList(items, target) {
  const list = $(target);
  list.replaceChildren();
  items.forEach((item) => {
    const row = element("li");
    row.append(element("p", null, item.text));
    const why = element("button", "why-link", "Why?");
    why.type = "button";
    setCitations(why, item.citations);
    row.append(why);
    list.append(row);
  });
}

function renderWorkflow(items) {
  const container = $("#workflow-items");
  container.replaceChildren();
  items.forEach((item) => {
    const block = element("div", "workflow-item");
    block.append(element("strong", null, item.system), element("span", null, item.status));
    container.append(block);
  });
}

function selectClient(clientId) {
  state.clientId = clientId;
  state.editing = false;
  $$('[data-screen="pre-read"], [data-screen="scenario"]').forEach((button) => {
    button.disabled = false;
  });
  renderPreRead();
  showScreen("pre-read");
}

function renderPreRead() {
  const preRead = state.data.pre_reads[state.clientId];
  $("#client-id").textContent = preRead.client_id;
  $("#client-name").textContent = preRead.name;
  $("#review-state").textContent = "Unreviewed";
  $("#review-state").className = "review-state";
  renderCitedList(preRead.what_changed, "#changed-list");
  $("#belief-text").textContent = `“${preRead.gap.belief}”`;
  $("#data-text").textContent = preRead.gap.data;
  setCitations($("#gap-why"), preRead.gap.citations);
  renderCitedList(preRead.rules_money, "#rules-list");
  $("#opening-language").textContent = preRead.language;
  $("#opening-text").textContent = preRead.opening.text;
  $("#edited-opening").value = preRead.opening.text;
  setCitations($("#opening-why"), preRead.opening.citations);
  $("#uncertainty-text").textContent = preRead.uncertainty.text;
  setCitations($("#uncertainty-why"), preRead.uncertainty.citations);
  renderWorkflow(preRead.workflow);
  $("#edit-panel").hidden = true;
  $("#review-receipt").hidden = true;
  $('[data-review="Edit"]').textContent = "Edit";
}

function showScreen(name) {
  if (name !== "list" && !state.clientId) return;
  $$(".screen").forEach((screen) => {
    screen.hidden = screen.id !== `${name}-screen`;
  });
  $$(".flow-nav button").forEach((button) => {
    const active = button.dataset.screen === name;
    if (active) button.setAttribute("aria-current", "step");
    else button.removeAttribute("aria-current");
  });
  if (name === "scenario") renderScenario();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function money(value, currency) {
  const sign = value >= 0 ? "+" : "−";
  return `${sign}${currency} ${Math.abs(value / 1_000_000).toFixed(1)}m`;
}

function renderScenario() {
  const scenario = state.data.scenarios[state.clientId][state.scenario];
  const preRead = state.data.pre_reads[state.clientId];
  $("#scenario-client").textContent = preRead.name;
  $("#scenario-name").textContent = scenario.name;
  $("#scenario-range").textContent = `${money(scenario.low_delta, scenario.currency)} to ${money(
    scenario.high_delta,
    scenario.currency,
  )}`;
  $("#scenario-percent").textContent = `${scenario.low_pct.toFixed(1)}% to ${scenario.high_pct.toFixed(
    1,
  )}% of today's portfolio`;
  renderCitedList(scenario.bullets, "#scenario-bullets");
  setCitations($("#scenario-why"), scenario.citations);

  const scale = (value) => Math.max(0, Math.min(100, ((value + 20) / 40) * 100));
  const left = scale(scenario.low_pct);
  const right = scale(scenario.high_pct);
  const line = $("#range-line");
  line.style.left = `${left}%`;
  line.style.width = `${Math.max(right - left, 1.5)}%`;
}

function setScenario(name) {
  state.scenario = name;
  $$("[data-scenario]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.scenario === name));
  });
  renderScenario();
}

function expandCitations(citations) {
  const facts = state.data.facts[state.clientId] || [];
  const factMap = Object.fromEntries(facts.map((fact) => [fact.id, fact]));
  const records = [];
  const queue = [...citations];
  const seen = new Set();
  while (queue.length) {
    const citation = queue.shift();
    if (!citation || seen.has(citation)) continue;
    seen.add(citation);
    const fact = factMap[citation];
    if (fact) {
      records.push({ type: "fact", value: fact });
      queue.push(...fact.source_rows, ...fact.event_ids);
      continue;
    }
    const evidence = state.data.evidence[citation];
    if (evidence) records.push({ type: "evidence", value: evidence });
  }
  return records;
}

function renderEvidenceRecord(item) {
  if (item.type === "fact") {
    const block = element("article", "evidence-record fact-record");
    block.append(element("h3", null, "Computed fact"));
    block.append(element("p", null, item.value.what));
    block.append(element("p", "evidence-source", `Confidence: ${item.value.confidence}`));
    return block;
  }
  const record = item.value;
  const block = element("article", "evidence-record");
  block.append(element("h3", null, record.title));
  block.append(element("p", "evidence-source", record.source));
  const details = element("dl");
  Object.entries(record.record).forEach(([key, value]) => {
    details.append(element("dt", null, key.replaceAll("_", " ")));
    details.append(element("dd", null, value === null ? "Not recorded" : String(value)));
  });
  block.append(details);
  return block;
}

function openEvidence(citations, trigger) {
  state.lastFocus = trigger;
  const content = $("#evidence-content");
  const records = expandCitations(citations);
  content.replaceChildren(
    ...(records.length
      ? records.map(renderEvidenceRecord)
      : [element("p", null, "Nothing in the source tables backs this one.")]),
  );
  $("#drawer-scrim").hidden = false;
  const drawer = $("#evidence-drawer");
  drawer.removeAttribute("inert");
  drawer.classList.add("is-open");
  drawer.setAttribute("aria-hidden", "false");
  $("#close-drawer").focus();
}

function closeEvidence() {
  $("#drawer-scrim").hidden = true;
  const drawer = $("#evidence-drawer");
  drawer.classList.remove("is-open");
  drawer.setAttribute("aria-hidden", "true");
  drawer.setAttribute("inert", "");
  state.lastFocus?.focus();
}

async function saveReview(action) {
  const edited = $("#edited-opening").value.trim();
  try {
    const payload = await request("/api/reviews", {
      method: "POST",
      body: JSON.stringify({
        client_id: state.clientId,
        action,
        text: action === "Edit" ? edited : $("#opening-text").textContent,
      }),
    });
    if (action === "Edit") {
      $("#opening-text").textContent = edited;
      $("#edit-panel").hidden = true;
      $('[data-review="Edit"]').textContent = "Edit";
      state.editing = false;
    }
    const reviewState = $("#review-state");
    const labels = { Approve: "Approved", Edit: "Edited", Reject: "Rejected" };
    reviewState.textContent = labels[action];
    reviewState.className = `review-state is-${labels[action].toLowerCase()}`;
    const receipt = $("#review-receipt");
    const time = new Date(payload.review.timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    receipt.textContent = `Review log · ${labels[action]} · ${time} · ${payload.review.rm}`;
    receipt.hidden = false;
    showToast(`${payload.review.action} recorded for ${state.data.pre_reads[state.clientId].name}.`);
  } catch (error) {
    showToast(error.message);
  }
}

function handleReview(action) {
  if (action !== "Edit") {
    saveReview(action);
    return;
  }
  if (!state.editing) {
    state.editing = true;
    $("#edit-panel").hidden = false;
    $('[data-review="Edit"]').textContent = "Save edit";
    $("#edited-opening").focus();
    return;
  }
  saveReview("Edit");
}

document.addEventListener("click", (event) => {
  const client = event.target.closest("[data-client]");
  if (client) return selectClient(client.dataset.client);

  const navigation = event.target.closest("[data-screen]");
  if (navigation && !navigation.disabled) return showScreen(navigation.dataset.screen);

  const scenario = event.target.closest("[data-scenario]");
  if (scenario) return setScenario(scenario.dataset.scenario);

  const review = event.target.closest("[data-review]");
  if (review) return handleReview(review.dataset.review);

  const why = event.target.closest("[data-citations]");
  if (why) return openEvidence(JSON.parse(why.dataset.citations), why);
});

$("#close-drawer").addEventListener("click", closeEvidence);
$("#drawer-scrim").addEventListener("click", closeEvidence);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && $("#evidence-drawer").classList.contains("is-open")) closeEvidence();
});

request("/api/app")
  .then((data) => {
    state.data = data;
    renderList();
  })
  .catch((error) => showToast(error.message));
