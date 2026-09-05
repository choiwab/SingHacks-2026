import { Button } from "@fluentui/react-components";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import type { components } from "./generated/openapi";
import "./MeetingPresentation.css";

type ClientView = components["schemas"]["ClientView"];
type DemoViewModel = components["schemas"]["DemoViewModel"];
type Json = components["schemas"]["JsonValue"];
const object = (value: Json | undefined): Record<string, Json> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, Json>)
    : {};
const text = (value: Json | undefined) =>
  typeof value === "string" ? value : "";
function claims(value: Json | undefined) {
  return (Array.isArray(value) ? value : value ? [value] : []).flatMap(
    (item) => {
      const claim = object(item);
      return text(claim.text)
        ? [
            {
              text: text(claim.text),
              citations: Array.isArray(claim.citations)
                ? claim.citations.filter(
                    (id): id is string => typeof id === "string",
                  )
                : [],
            },
          ]
        : [];
    },
  );
}

export function MeetingPresentation({
  client,
  model,
  onClose,
}: {
  client: ClientView;
  model: DemoViewModel;
  onClose: () => void;
}) {
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const prior = document.activeElement;
    const siblings = Array.from(document.body.children).filter(
      (element): element is HTMLElement =>
        element instanceof HTMLElement &&
        !element.classList.contains("meeting-presentation-root"),
    );
    const inertBefore = siblings.map((element) => element.inert);
    siblings.forEach((element) => {
      element.inert = true;
    });
    document.body.classList.add("presenting-meeting");
    closeButton.current?.focus();
    return () => {
      siblings.forEach((element, index) => {
        element.inert = inertBefore[index];
      });
      document.body.classList.remove("presenting-meeting");
      if (prior instanceof HTMLElement && prior.isConnected) prior.focus();
    };
  }, []);
  const reviews = (model.reviews ?? []).filter(
    (review) =>
      review.client_id === client.header.client_id &&
      review.run_id === model.run_id &&
      review.brief_version === client.brief_version,
  );
  const latest = reviews.at(-1);
  const checks = client.verification?.checks ?? [];
  const hasErrors = (value: Json) =>
    Array.isArray(value) ? value.length > 0 : Boolean(value);
  const checksList = Array.isArray(checks)
    ? checks
    : Object.values(object(checks));
  const verificationFailed =
    client.verification?.passed !== true ||
    hasErrors(client.verification?.errors) ||
    (!Array.isArray(checks) &&
      (checks === null || typeof checks !== "object")) ||
    checksList.some(
      (check) =>
        check !== true &&
        (object(check).passed !== true || hasErrors(object(check).errors)),
    );
  const blocked =
    !client.meeting_brief ||
    verificationFailed ||
    (client.context_issues?.length ?? 0) > 0 ||
    client.quality_findings?.some((finding) => finding.severity === "error");
  const approved =
    !blocked && client.brief_status === "Ready" && latest?.action === "Approve";
  const status = blocked
    ? "Unavailable for presentation"
    : model.data_health === "Stale"
      ? "Stale data: check before use"
      : latest?.action === "Reject"
        ? "Rejected"
        : approved
          ? "Reviewed Meeting Brief"
          : "Draft: needs Relationship Manager review";
  const sections = object(client.meeting_brief?.sections);
  const content = [
    { title: "Open the conversation", entries: claims(sections.opening) },
    { title: "At a glance", entries: claims(sections.summary) },
    {
      title: "Discussion topics",
      entries: claims(sections.talking_points ?? sections.discussion_topics),
    },
    { title: "You said / Data says", entries: claims(sections.discrepancy) },
    {
      title: "Questions to ask",
      entries: claims(sections.questions ?? sections.suggested_questions),
    },
    { title: "What remains uncertain", entries: claims(sections.uncertainty) },
  ];
  const references = [
    ...new Set(
      content.flatMap((section) =>
        section.entries.flatMap((claim) => claim.citations),
      ),
    ),
  ];
  const facts = Object.values(client.data_tab).flat();
  function sourceLabel(id: string) {
    const fact = facts.find(
      (item) => item.id === id && item.client_id === client.header.client_id,
    );
    if (fact)
      return `Fact · ${fact.id} · ${fact.evidence_ids?.join(", ") || "Source reference unavailable"}`;
    // Only render metadata for explicitly cited sources, never the global record payload.
    const evidence = model.evidence?.[id];
    if (evidence)
      return `${evidence.title} · ${evidence.source_file || evidence.source}${evidence.row_index == null ? "" : ` · row ${evidence.row_index}`}`;
    const connected = object(model.connected_evidence?.[id]);
    const record = object(connected.record);
    if (Object.keys(connected).length)
      return `Connected Record · ${text(record.connector) || text(connected.connector) || "Connector unspecified"} · ${text(record.state) || text(connected.state) || "Availability unspecified"}`;
    return "Source detail unavailable in this view";
  }
  return createPortal(
    <div
      className="meeting-presentation-root"
      role="dialog"
      aria-modal="true"
      aria-labelledby="presentation-title"
      onKeyDown={(event) => {
        if (event.key === "Escape") onClose();
        if (event.key === "Tab") {
          const buttons = Array.from(
            event.currentTarget.querySelectorAll<HTMLButtonElement>(
              "button:not(:disabled)",
            ),
          );
          const first = buttons[0];
          const last = buttons.at(-1);
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last?.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first?.focus();
          }
        }
      }}
    >
      <div className="meeting-presentation-controls">
        <Button ref={closeButton} onClick={onClose}>
          Back to preparation
        </Button>
        <span>Relationship Manager preparation</span>
        <Button onClick={() => window.print()} disabled={blocked}>
          Print Meeting Brief
        </Button>
      </div>
      <article className="meeting-document">
        <header className="meeting-document-header">
          <p className="meeting-document-brand">Client Future Room</p>
          <p className="meeting-document-status" role="status">
            {status}
          </p>
          <h1 id="presentation-title">
            A conversation with
            <br />
            {client.header.client_name}
          </h1>
          <p className="meeting-document-intro">
            Meeting Brief · Internal Relationship Manager preparation
          </p>
          <dl className="meeting-document-metadata">
            <div>
              <dt>As-of Date</dt>
              <dd>{model.as_of}</dd>
            </div>
            <div>
              <dt>Brief version</dt>
              <dd>{client.brief_version ?? "Not available"}</dd>
            </div>
            <div>
              <dt>Data health</dt>
              <dd>{model.data_health}</dd>
            </div>
            <div className="meeting-document-run">
              <dt>Pipeline Run</dt>
              <dd>{model.run_id}</dd>
            </div>
          </dl>
          <p className="meeting-document-notice">
            Generated preparation. Review does not authorise client
            distribution. Requested reporting language:{" "}
            {client.header.reporting_language}. No translation is applied in
            this view.
          </p>
          {latest && (
            <p className="meeting-document-notice">
              Current Review Decision: {latest.action} · {latest.rm} ·{" "}
              {latest.timestamp}
            </p>
          )}
        </header>
        {blocked ? (
          <section>
            <h2>Meeting Brief is not available</h2>
            <p>
              Return to preparation to resolve the Evidence Gate or context
              issues before presenting or printing.
            </p>
          </section>
        ) : (
          <>
            <div className="meeting-document-content">
              {content
                .filter((section) => section.entries.length > 0)
                .map((section) => (
                  <section key={section.title}>
                    <h2>{section.title}</h2>
                    {section.entries.map((claim, index) => (
                      <p key={index}>
                        {claim.text}
                        {claim.citations.length > 0 && (
                          <sup
                            aria-label={`Evidence references ${claim.citations.map((id) => references.indexOf(id) + 1).join(", ")}`}
                          >
                            {" "}
                            [
                            {claim.citations
                              .map((id) => references.indexOf(id) + 1)
                              .join(", ")}
                            ]
                          </sup>
                        )}
                      </p>
                    ))}
                  </section>
                ))}
              {content.every((section) => section.entries.length === 0) && (
                <p>No supported Meeting Brief sections are available.</p>
              )}
            </div>
            <section className="meeting-document-sources">
              <h2>Supporting Evidence</h2>
              {references.length ? (
                <ol>
                  {references.map((id) => (
                    <li key={id}>
                      <strong>{id}</strong>
                      <br />
                      {sourceLabel(id)}
                    </li>
                  ))}
                </ol>
              ) : (
                <p>No Evidence references supplied.</p>
              )}
            </section>
          </>
        )}
        {client.quality_findings
          ?.filter((finding) => finding.severity === "warning")
          .map((finding, index) => (
            <p className="meeting-document-notice" key={index}>
              Data Quality Finding: {finding.message}
            </p>
          ))}
        <footer className="meeting-document-footer">
          {status} · As-of Date {model.as_of} · Brief version{" "}
          {client.brief_version ?? "unavailable"}
        </footer>
      </article>
    </div>,
    document.body,
  );
}
