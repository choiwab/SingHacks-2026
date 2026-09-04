const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];

const WEEK = [
  { key: "Mon", label: "Mon", date: "31 Aug" },
  { key: "Tue", label: "Tue", date: "1 Sep" },
  { key: "Wed", label: "Wed", date: "2 Sep" },
  { key: "Thu", label: "Thu", date: "3 Sep" },
  { key: "Fri", label: "Fri", date: "4 Sep" },
];

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
    throw new Error(payload.detail || "The server did not answer. Try again.");
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

function priorityMeta(client, index) {
  const meta = element("span", "priority-meta");
  meta.append(
    element("span", "priority-rank", `#${index + 1}`),
    element("span", null, client.score.toFixed(0)),
  );
  return meta;
}

function renderCallRow(client, index) {
  const row = element("button", `call-row urgency-${client.urgency}`);
  row.type = "button";
  row.dataset.client = client.client_id;

  const copy = element("span", "client-copy");
  copy.append(
    element("strong", "client-name", client.name),
    element("span", "client-reason", client.reason),
  );
  row.append(priorityMeta(client, index), copy, element("span", "row-action", "Open →"));
  return row;
}

function renderMeetingCard(client, index) {
  const card = element("button", `meeting-card urgency-${client.urgency}`);
  card.type = "button";
  card.dataset.client = client.client_id;
  const time = client.meeting.split(" ").slice(1).join(" ");

  const top = element("span", "meeting-meta");
  top.append(element("span", null, `#${index + 1} · ${client.score}`), element("span", null, time));
  card.append(
    top,
    element("strong", "meeting-client", client.name),
    element("span", "meeting-reason", client.reason),
    element("span", "meeting-action", "Open pre-read →"),
  );
  return card;
}

function renderList() {
  const callList = $("#call-list");
  const meetingGrid = $("#meeting-grid");
  const calls = state.data.ranking.filter((client) => !client.meeting);
  const meetings = state.data.ranking.filter((client) => client.meeting);
  const ranks = new Map(state.data.ranking.map((client, index) => [client.client_id, index]));

  callList.replaceChildren(...calls.map((client) => renderCallRow(client, ranks.get(client.client_id))));
  $("#call-count").textContent = calls.length;
  $("#meeting-count").textContent = meetings.length;

  const days = WEEK.map((day) => {
    const column = element("section", "day-column");
    const heading = element("header", "day-heading");
    heading.append(element("span", null, day.label), element("strong", null, day.date));
    column.append(heading);

    const dayMeetings = meetings.filter((client) => client.meeting.startsWith(day.key));
    column.classList.toggle("is-empty", dayMeetings.length === 0);
    if (dayMeetings.length) {
      dayMeetings.forEach((client) => column.append(renderMeetingCard(client, ranks.get(client.client_id))));
    } else {
      column.append(element("p", "open-day", "Open for preparation"));
    }
    return column;
  });
  meetingGrid.replaceChildren(...days);

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
    const block = element("article", "workflow-item");
    const copy = element("div");
    copy.append(element("strong", null, item.system), element("span", null, item.status));
    block.append(copy);
    if (item.citations?.length) {
      const why = element("button", "why-link", "Why?");
      why.type = "button";
      setCitations(why, item.citations);
      block.append(why);
    }
    container.append(block);
  });
}

function selectClient(clientId) {
  state.clientId = clientId;
  state.scenario = "reopens";
  state.editing = false;
  $$('[data-scenario]').forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.scenario === "reopens"));
  });
  $$('[data-screen="pre-read"], [data-screen="scenario"]').forEach((button) => {
    button.disabled = false;
  });
  renderPreRead();
  showScreen("pre-read");
}

function renderPreRead() {
  const preRead = state.data.pre_reads[state.clientId];
  const rank = state.data.ranking.findIndex((client) => client.client_id === state.clientId);
  const rankedClient = state.data.ranking[rank];
  $("#client-id").textContent = preRead.client_id;
  $("#client-name").textContent = preRead.name;
  $("#client-priority").textContent = `#${rank + 1} · score ${rankedClient.score}`;
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
  $$(".product-nav button").forEach((button) => {
    const active = button.dataset.screen === name;
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  const titles = { list: "Monday list", "pre-read": "Pre-read", scenario: "Scenario rehearsal" };
  document.title = `${titles[name]} | Wealth Intelligence`;
  if (name === "scenario") renderScenario();
  window.scrollTo({ top: 0, behavior: "auto" });
}

function money(value, currency) {
  const sign = value >= 0 ? "+" : "−";
  return `${sign}${currency} ${Math.abs(value / 1_000_000).toFixed(1)}m`;
}

function percent(value) {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(1)}%`;
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
  $("#scenario-percent").textContent =
    `${percent(scenario.low_pct)} to ${percent(scenario.high_pct)} of today's portfolio`;
  renderCitedList(scenario.bullets, "#scenario-bullets");
  setCitations($("#scenario-why"), scenario.citations);

  const scale = (value) => Math.max(0, Math.min(100, ((value + 20) / 40) * 100));
  const left = scale(scenario.low_pct);
  const right = scale(scenario.high_pct);
  const line = $("#range-line");
  line.style.left = `${left}%`;
  line.style.width = `${Math.max(right - left, 1.5)}%`;

  const result = $(".scenario-result");
  result.classList.toggle("is-positive", scenario.low_pct >= 0);
  result.classList.toggle("is-negative", scenario.high_pct <= 0);
}

function setScenario(name) {
  state.scenario = name;
  $$('[data-scenario]').forEach((button) => {
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
    block.append(element("p", "record-type", "Computed fact"));
    block.append(element("h3", null, item.value.what));
    block.append(element("p", "evidence-source", `Confidence: ${item.value.confidence}`));
    return block;
  }
  const record = item.value;
  const block = element("article", "evidence-record");
  block.append(element("p", "record-type", record.kind || "Source row"));
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
  const records = expandCitations(citations);
  $("#evidence-content").replaceChildren(
    ...(records.length
      ? records.map(renderEvidenceRecord)
      : [element("p", null, "No source row is attached to this line.")]),
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
  const buttons = $$("[data-review]");
  buttons.forEach((button) => {
    button.disabled = true;
  });
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
    const labels = { Approve: "Approved", Edit: "Edited", Reject: "Rejected" };
    const reviewState = $("#review-state");
    reviewState.textContent = labels[action];
    reviewState.className = `review-state is-${labels[action].toLowerCase()}`;
    const receipt = $("#review-receipt");
    const time = new Date(payload.review.timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    receipt.textContent = `Review log · ${labels[action]} · ${time} · ${payload.review.rm}`;
    receipt.hidden = false;
    showToast(`${labels[action]} for ${state.data.pre_reads[state.clientId].name}.`);
  } catch (error) {
    showToast(error.message);
  } finally {
    buttons.forEach((button) => {
      button.disabled = false;
    });
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
