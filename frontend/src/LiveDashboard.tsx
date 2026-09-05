import {
  Button,
  Field,
  MessageBar,
  MessageBarBody,
  Select,
  Spinner,
  Textarea,
} from "@fluentui/react-components";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getDemoViewModel, saveLiveReview } from "./api";
import {
  briefSections,
  claim,
  claims,
  clientFacts,
  factValue,
  record,
  text,
  type Claim,
  type ClientView,
  type DemoViewModel,
} from "./live-contracts";
import { EvidenceButton } from "./LiveEvidence";
import "./live.css";

function ClaimText({
  value,
  model,
  client,
}: {
  value: Claim;
  model: DemoViewModel;
  client: ClientView;
}) {
  return (
    <div className="live-claim">
      <p>{value.text}</p>
      <small>
        {value.authorship === "rm"
          ? "Relationship Manager edited"
          : "Verified generated content"}
      </small>
      <div>
        {value.citations.map((id) => (
          <EvidenceButton key={id} id={id} model={model} client={client} />
        ))}
      </div>
    </div>
  );
}

function Continuity({
  client,
  model,
}: {
  client: ClientView;
  model: DemoViewModel;
}) {
  const interactions = (client.memory_tab ?? []).filter(
    (item) =>
      item.source !== "calendar" &&
      !["calendar", "meeting"].includes(text(item.type ?? item.kind)) &&
      text(item.occurred_at ?? item.note_date ?? item.date).slice(0, 10) <=
        model.as_of &&
      text(item.occurred_at ?? item.note_date ?? item.date),
  );
  const last = [...interactions].sort((a, b) =>
    text(b.occurred_at ?? b.note_date ?? b.date).localeCompare(
      text(a.occurred_at ?? a.note_date ?? a.date),
    ),
  )[0];
  const promises = claims(record(client.memory_card?.open_promises).claims);
  const promiseReference = promises[0]?.citations[0];
  const promiseEvidence = promiseReference
    ? model.connected_evidence?.[promiseReference]
    : undefined;
  const promiseRecord = record(
    promiseEvidence?.record ??
      promiseEvidence ??
      client.memory_tab?.find(
        (item) =>
          item.id === promiseReference || item.evidence_id === promiseReference,
      ),
  );
  const promiseDate = text(
    promiseRecord.occurred_at ?? promiseRecord.note_date ?? promiseRecord.date,
  );
  const changedIds = new Set(client.change_report.changed_fact_ids ?? []);
  const fact = clientFacts(client).find((item) => changedIds.has(item.id));
  const questions = claims(briefSections(client).questions);
  return (
    <section className="live-continuity" aria-labelledby="continuity-title">
      <div className="live-section-heading">
        <span className="live-eyebrow">Relationship continuity</span>
        <h2 id="continuity-title">Since we last spoke</h2>
      </div>
      <div className="live-continuity-grid">
        <article>
          <h3>Last dated interaction</h3>
          {last ? (
            <>
              <p className="live-date">
                {text(last.occurred_at ?? last.note_date ?? last.date)}
              </p>
              <p className="live-source-excerpt">
                {text(
                  last.text ?? last.note ?? last.note_text ?? last.content,
                ) || "Open the Source Record for its exact fields."}
              </p>
              <small>
                {text(last.source) || "RM note"} ·{" "}
                {text(last.availability) || "Dataset record"}
                {last.provenance ? ` · ${text(last.provenance)}` : ""}
              </small>
              <div>
                <EvidenceButton
                  id={text(last.id ?? last.evidence_id)}
                  model={model}
                  client={client}
                />
              </div>
            </>
          ) : (
            <p>
              No dated interaction available. Confirm the last conversation with
              the Relationship Manager.
            </p>
          )}
        </article>
        <article>
          <h3>Unresolved commitment</h3>
          {promises[0] ? (
            <>
              <p className="live-date">
                {promiseDate || "Source date unavailable"}
              </p>
              <ClaimText value={promises[0]} model={model} client={client} />
            </>
          ) : (
            <p>
              No verified open promise or unresolved question available. This
              does not confirm that every commitment is complete.
            </p>
          )}
        </article>
        <article>
          <h3>{fact ? "Changed Fact" : "Change not established"}</h3>
          {fact ? (
            <>
              <p>{fact.kind}</p>
              <p className="live-fact-value">{factValue(fact)}</p>
              <small>
                As-of Date {fact.as_of}. Compared with the prior Pipeline Run,
                not necessarily the last interaction.
              </small>
              <div>
                <EvidenceButton id={fact.id} model={model} client={client} />
              </div>
            </>
          ) : (
            <p>
              No changed Fact is identified in this Pipeline Run. A change since
              the last interaction has not been established.
            </p>
          )}
        </article>
      </div>
      {questions[0] && (
        <div className="live-meeting-question">
          <h3>Suggested meeting question</h3>
          <ClaimText value={questions[0]} model={model} client={client} />
        </div>
      )}
    </section>
  );
}

function ClientWorkspace({
  client,
  model,
  onModelChange,
  busy,
  setBusy,
}: {
  client: ClientView;
  model: DemoViewModel;
  onModelChange: (model: DemoViewModel) => void;
  busy: boolean;
  setBusy: (busy: boolean) => void;
}) {
  const opening = claim(briefSections(client).opening);
  const editable = [
    opening,
    ...claims(briefSections(client).talking_points),
  ].filter((item): item is Claim => item !== null);
  const [section, setSection] = useState(editable[0]?.id ?? "");
  const [draft, setDraft] = useState(editable[0]?.text ?? "");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function review(action: "Approve" | "Edit" | "Reject") {
    if (client.brief_version == null) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await saveLiveReview({
        client_id: client.header.client_id,
        run_id: model.run_id,
        brief_version: client.brief_version,
        action,
        text: action === "Edit" ? draft : "",
        section: action === "Edit" ? section : null,
      });
      setNotice(
        `${action} decision saved. Refreshing the current Meeting Brief.`,
      );
      onModelChange(await getDemoViewModel());
      setEditing(false);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Review could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }
  const canReview =
    client.meeting_brief != null && client.brief_version != null;
  const currentReviews = (model.reviews ?? []).filter(
    (item) =>
      item.client_id === client.header.client_id &&
      item.run_id === model.run_id &&
      item.brief_version === client.brief_version,
  );
  const lastReview = currentReviews.at(-1);
  return (
    <>
      <header className="live-client-heading">
        <div>
          <span className="live-eyebrow">Meeting preparation</span>
          <h1>{client.header.client_name}</h1>
          <p>
            {client.header.life_stage} · {client.header.risk_profile} ·
            Reporting currency {client.header.base_currency}
          </p>
        </div>
        <span
          className={`live-status ${client.brief_status === "Ready" ? "live-status-ready" : ""}`}
        >
          {client.brief_status === "Ready"
            ? "Reviewed meeting pack"
            : client.brief_status}
        </span>
      </header>
      <Continuity client={client} model={model} />
      {/* BriefHistoryPanel mounts here after its stacked change. */}
      <section className="live-brief" aria-labelledby="brief-title">
        <div className="live-section-heading">
          <span className="live-eyebrow">Preparation for the conversation</span>
          <h2 id="brief-title">Meeting Brief</h2>
          <p>
            Version {client.brief_version ?? "not available"} ·{" "}
            {client.brief_status}
          </p>
        </div>
        {!client.meeting_brief ? (
          <MessageBar intent="warning">
            <MessageBarBody>
              No verified Meeting Brief is available. The Evidence Gate has not
              released generated content for review. Source Records and
              deterministic Facts remain available below.
            </MessageBarBody>
          </MessageBar>
        ) : (
          <>
            {opening && (
              <>
                <h3>Suggested opening</h3>
                <ClaimText value={opening} model={model} client={client} />
              </>
            )}
            {(
              [
                ["Discussion topics", "talking_points"],
                ["Summary", "summary"],
                ["Questions", "questions"],
                ["Uncertainty", "uncertainty"],
              ] as const
            ).map(([label, key]) => (
              <div key={key}>
                <h3>{label}</h3>
                {claims(briefSections(client)[key]).map((item) => (
                  <ClaimText
                    key={item.id}
                    value={item}
                    model={model}
                    client={client}
                  />
                ))}
              </div>
            ))}
          </>
        )}
        {lastReview && (
          <p role="status">
            Latest decision: {lastReview.action} · {lastReview.rm} ·{" "}
            {lastReview.timestamp}
          </p>
        )}
        {notice && <p role="status">{notice}</p>}
        {error && (
          <MessageBar intent="error">
            <MessageBarBody>
              {error} Reload the current version before trying again. Your draft
              remains visible until reload.
            </MessageBarBody>
          </MessageBar>
        )}
        {editing && (
          <div className="live-editor">
            <Field label="Section to edit">
              <Select
                value={section}
                onChange={(_, data) => {
                  setSection(data.value);
                  setDraft(
                    editable.find((item) => item.id === data.value)?.text ?? "",
                  );
                }}
              >
                {editable.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.id}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Relationship Manager wording">
              <Textarea
                value={draft}
                maxLength={1200}
                resize="vertical"
                onChange={(_, data) => setDraft(data.value)}
              />
            </Field>
            <p>
              Saving creates a new version and runs the Evidence Gate again.
              Approval requires a separate Review Decision.
            </p>
            <Button
              disabled={busy || !draft.trim()}
              onClick={() => void review("Edit")}
            >
              Save edited version
            </Button>
          </div>
        )}
        <div className="live-actions">
          <Button
            appearance="primary"
            disabled={busy || !canReview || editing}
            onClick={() => void review("Approve")}
          >
            Approve Meeting Brief
          </Button>
          <Button
            disabled={busy || !canReview || !editable.length}
            onClick={() => setEditing(!editing)}
          >
            {editing ? "Cancel edit" : "Edit wording"}
          </Button>
          <Button
            disabled={busy || !canReview || editing}
            onClick={() => void review("Reject")}
          >
            Reject Meeting Brief
          </Button>
        </div>
      </section>
      <section className="live-details" aria-label="Data health and Evidence">
        <h2>Data health and Evidence</h2>
        {(client.context_issues ?? []).map((issue) => (
          <p key={issue}>{issue}</p>
        ))}
        {(client.quality_findings ?? []).map((finding, i) => (
          <article key={`${finding.code}-${i}`}>
            <h3>
              {finding.severity}: {finding.code}
            </h3>
            <p>{finding.message}</p>
            {finding.evidence_ids?.map((id) => (
              <EvidenceButton key={id} id={id} model={model} client={client} />
            ))}
          </article>
        ))}
        <details>
          <summary>Verification Report</summary>
          <pre>{JSON.stringify(client.verification, null, 2)}</pre>
        </details>
        {Object.entries(client.data_tab).map(([group, facts]) => (
          <details key={group}>
            <summary>{group.replaceAll("_", " ")}</summary>
            {facts?.map((fact) => (
              <article key={fact.id}>
                <h3>{fact.kind}</h3>
                <p>{factValue(fact)}</p>
                <EvidenceButton id={fact.id} model={model} client={client} />
              </article>
            ))}
          </details>
        ))}
        <details>
          <summary>Connected Records and RM notes</summary>
          {client.memory_tab?.map((item, i) => (
            <pre key={i}>{JSON.stringify(item, null, 2)}</pre>
          ))}
        </details>
      </section>
    </>
  );
}

export function LiveDashboard() {
  const [model, setModel] = useState<DemoViewModel | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    let active = true;
    getDemoViewModel()
      .then((data) => {
        if (active) {
          setBusy(false);
          setModel(data);
          setError("");
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setBusy(false);
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not load the dashboard.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [attempt]);
  const routeId = location.pathname.match(/^\/clients\/([^/]+)/)?.[1];
  const firstMeetingId = model?.calendar
    ?.map((meeting) => text(meeting.client_id))
    .find((id) => model.clients[id]);
  const clientId =
    routeId ?? firstMeetingId ?? Object.keys(model?.clients ?? {})[0];
  const client = model?.clients[clientId];
  function selectClient(id: string) {
    navigate(`/clients/${encodeURIComponent(id)}/pre-read`);
  }
  return (
    <div className="live-app">
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <header className="live-topbar">
        <strong>Client Future Room</strong>
        <span>Relationship Manager workspace</span>
        <Button
          disabled={busy}
          onClick={() => {
            setBusy(true);
            setError("");
            setAttempt((value) => value + 1);
          }}
        >
          Reload current version
        </Button>
      </header>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>
            {error}{" "}
            <Button onClick={() => setAttempt((value) => value + 1)}>
              Try again
            </Button>
          </MessageBarBody>
        </MessageBar>
      )}
      {!model ? (
        !error && (
          <main className="app-status">
            <Spinner label="Loading the live dashboard…" />
          </main>
        )
      ) : (
        <>
          <nav className="live-meetings" aria-label="Booked meetings">
            <div>
              <h2>Booked meetings</h2>
              <small>
                As-of Date {model.as_of} · Data health: {model.data_health}
              </small>
            </div>
            {model.calendar?.length ? (
              model.calendar.map((meeting, i) => (
                <Button
                  key={text(meeting.id) || i}
                  disabled={busy || !model.clients[text(meeting.client_id)]}
                  onClick={() => selectClient(text(meeting.client_id))}
                >
                  {model.clients[text(meeting.client_id)]?.header.client_name ??
                    "Unknown client"}{" "}
                  ·{" "}
                  {text(
                    meeting.scheduled_at ??
                      meeting.start_time ??
                      meeting.occurred_at,
                  ) || "Time unavailable"}{" "}
                  · {text(meeting.availability) || "State unavailable"}
                </Button>
              ))
            ) : (
              <p>
                No booked meeting is available from the connected calendar.
                Select a client to prepare.
              </p>
            )}
          </nav>
          <div className="live-selection">
            <Field label="Selected client">
              <Select
                disabled={busy}
                value={clientId ?? ""}
                onChange={(_, data) => selectClient(data.value)}
              >
                {Object.entries(model.clients).map(([id, item]) => (
                  <option key={id} value={id}>
                    {item.header.client_name}
                  </option>
                ))}
              </Select>
            </Field>
            <small>
              Pipeline Run <span className="live-id">{model.run_id}</span> ·
              Refreshed {model.refreshed_at}
            </small>
          </div>
          <main id="main" className="live-main" tabIndex={-1}>
            {client ? (
              <ClientWorkspace
                key={`${clientId}:${model.run_id}:${client.brief_version}`}
                client={client}
                model={model}
                onModelChange={setModel}
                busy={busy}
                setBusy={setBusy}
              />
            ) : (
              <p>Client not found. Select an available client above.</p>
            )}
          </main>
        </>
      )}
    </div>
  );
}
