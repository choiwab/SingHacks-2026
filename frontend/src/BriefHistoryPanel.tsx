import { useEffect, useRef, useState } from "react";
import type { components } from "./generated/openapi";
import {
  controlledUpdate,
  getBriefHistory,
  type BriefVersion,
  type ClientHistory,
  type DemoViewModel,
} from "./brief-history-api";
import "./brief-history.css";

type ClientView = components["schemas"]["ClientView"];
type Props = {
  client: ClientView;
  runId: string;
  refreshedAt?: string;
  onModelChange: (model: DemoViewModel) => void;
  busy?: boolean;
  onBusyChange?: (busy: boolean) => void;
};
type Claim = { id: string; section: string; text: string; citations: string[] };
function record(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}
function claims(brief: BriefVersion["meeting_brief"]): Claim[] {
  const sections = record(brief?.sections);
  if (!sections) return [];
  return Object.entries(sections).flatMap(([section, value]) =>
    (Array.isArray(value) ? value : [value]).flatMap((value, index) => {
      const claim = record(value);
      return claim && typeof claim.text === "string"
        ? [
            {
              id:
                typeof claim.id === "string" ? claim.id : `${section}:${index}`,
              section: section.replaceAll("_", " "),
              text: claim.text,
              citations: Array.isArray(claim.citations)
                ? claim.citations.filter(
                    (id): id is string => typeof id === "string",
                  )
                : [],
            },
          ]
        : [];
    }),
  );
}
function versionKey(version: BriefVersion) {
  return `${version.run_id}:${version.brief_version}`;
}
function VersionCard({
  version,
  title,
  other,
  compare,
  clientId,
}: {
  version?: BriefVersion;
  title: string;
  other?: BriefVersion;
  compare: boolean;
  clientId: string;
}) {
  if (!version)
    return (
      <article className="brief-version">
        <h3>{title}</h3>
        <p>No previous Meeting Brief is available.</p>
      </article>
    );
  // History only publishes verified bodies. Never extract claims from traces or reviews.
  const content = claims(version.meeting_brief);
  const otherClaims = claims(other?.meeting_brief ?? null);
  return (
    <article className="brief-version" aria-label={title}>
      <h3>{title}</h3>
      <p className="brief-version-meta">
        Version {version.brief_version} ·{" "}
        {version.origin === "rm_edited" ? "RM edited" : "Generated"}
      </p>
      <p className="brief-version-run">
        Pipeline Run <code>{version.run_id}</code>
      </p>
      <time dateTime={version.created_at}>{version.created_at}</time>
      {!version.meeting_brief ? (
        <p className="brief-history-notice">
          Evidence Gate has not passed. Meeting Brief content is withheld.
        </p>
      ) : content.length === 0 ? (
        <p>No displayable Meeting Brief claims are available.</p>
      ) : (
        content.map((claim) => {
          const previous = otherClaims.find(
            (item) => item.id === claim.id && item.section === claim.section,
          );
          const changed =
            compare &&
            other?.meeting_brief != null &&
            previous?.text !== claim.text;
          return (
            <div
              className={`brief-version-claim${changed ? " is-changed" : ""}`}
              key={`${claim.section}:${claim.id}`}
            >
              <span className="brief-version-label">
                {claim.section}
                {changed ? " · Changed" : ""}
              </span>
              <p>{claim.text}</p>
              {claim.citations.length > 0 && (
                <p className="brief-version-citations">
                  Evidence IDs: {claim.citations.join(", ")}
                </p>
              )}
            </div>
          );
        })
      )}
      <details className="brief-version-reviews">
        <summary>Review Decisions for this version</summary>
        {(version.reviews ?? []).filter(
          (review) =>
            review.client_id === clientId &&
            review.run_id === version.run_id &&
            review.brief_version === version.brief_version,
        ).length === 0 ? (
          <p>No Review Decision recorded.</p>
        ) : (
          (version.reviews ?? [])
            .filter(
              (review) =>
                review.client_id === clientId &&
                review.run_id === version.run_id &&
                review.brief_version === version.brief_version,
            )
            .map((review) => (
              <div key={review.review_id}>
                <p>
                  <strong>{review.action}</strong> · {review.rm} ·{" "}
                  {review.timestamp}
                </p>
                <p>
                  Review <code>{review.review_id}</code> · Run{" "}
                  <code>{review.run_id}</code> · Version {review.brief_version}
                </p>
              </div>
            ))
        )}
      </details>
    </article>
  );
}

export function BriefHistoryPanel(props: Props) {
  // Remount scoped reads immediately, so another Client's history never flashes.
  return (
    <HistorySession
      key={`${props.client.header.client_id}:${props.runId}:${props.client.brief_version}:${props.client.brief_status}:${props.refreshedAt ?? ""}`}
      {...props}
    />
  );
}
function HistorySession({
  client,
  runId,
  onModelChange,
  busy = false,
  onBusyChange,
}: Props) {
  const [history, setHistory] = useState<ClientHistory>();
  const [error, setError] = useState<string>();
  const [attempt, setAttempt] = useState(0);
  const [selection, setSelection] = useState<string>();
  const [pending, setPending] = useState(false);
  const [updateError, setUpdateError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const updateInFlight = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    getBriefHistory(client.header.client_id, runId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) {
          setHistory(value);
          setError(undefined);
        }
      })
      .catch((reason) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error
              ? reason.message
              : "Unable to load history.",
          );
      });
    return () => controller.abort();
  }, [client.header.client_id, runId, attempt]);
  const latest = history?.versions[0];
  const current =
    latest?.run_id === runId && latest.brief_version === client.brief_version
      ? latest
      : undefined;
  const prior =
    history?.versions.filter(
      (version) => versionKey(version) !== (current && versionKey(current)),
    ) ?? [];
  const selected =
    prior.find((version) => versionKey(version) === selection) ?? prior[0];
  async function update(action: "apply" | "reset") {
    if (busy || updateInFlight.current) return;
    updateInFlight.current = true;
    setPending(true);
    setUpdateError(undefined);
    setNotice(undefined);
    onBusyChange?.(true);
    try {
      const model = await controlledUpdate(action);
      onModelChange(model);
      setHistory(undefined);
      setError(undefined);
      setAttempt((value) => value + 1);
      setNotice(
        action === "reset"
          ? "Seed Pipeline Run restored. Its latest persisted Meeting Brief and Review Decisions are retained."
          : "Controlled Update applied. Review the returned Meeting Brief and its current review state.",
      );
    } catch (reason) {
      setUpdateError(
        reason instanceof Error ? reason.message : "Controlled Update failed.",
      );
    } finally {
      updateInFlight.current = false;
      setPending(false);
      onBusyChange?.(false);
    }
  }
  return (
    <section className="brief-history" aria-labelledby="brief-history-heading">
      <div className="brief-history-heading">
        <div>
          <span className="brief-version-label">
            Prepare · Compare · Review
          </span>
          <h2 id="brief-history-heading">What changed in the Meeting Brief?</h2>
        </div>
        <div className="brief-history-actions">
          <button
            disabled={busy || pending}
            onClick={() => void update("apply")}
          >
            Apply Controlled Update
          </button>
          <button
            disabled={busy || pending}
            onClick={() => void update("reset")}
          >
            Reset to seed run
          </button>
        </div>
      </div>
      <p>
        Compare the exact wording and Review Decisions across Pipeline Runs and
        Brief versions. Earlier approvals apply only to their recorded run and
        version.
      </p>
      <p className="brief-history-reset-note">
        Reset selects the seed Pipeline Run and retains its latest saved Brief
        and reviews.
      </p>
      {pending && (
        <p role="status">
          Updating Source Records and refreshing the Meeting Brief…
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {updateError && (
        <p role="alert">
          {updateError} The workspace may be out of date. Reload it before
          reviewing, then retry the update if needed.
        </p>
      )}
      {error ? (
        <div role="alert">
          <p>{error}</p>
          <button
            onClick={() => {
              setHistory(undefined);
              setError(undefined);
              setAttempt((value) => value + 1);
            }}
          >
            Retry history
          </button>
        </div>
      ) : !history ? (
        <p role="status">Loading Meeting Brief history…</p>
      ) : history.versions.length === 0 ? (
        <p>
          No saved Meeting Brief versions yet. Unverified or missing content
          cannot be reviewed.
        </p>
      ) : !current ? (
        <p role="alert">
          History and the current Brief version differ. Reload the workspace
          before comparing or reviewing.
        </p>
      ) : (
        <>
          <p className="brief-history-notice">
            Current Meeting Brief: <strong>{client.brief_status}</strong> ·
            Version {client.brief_version} · Run <code>{runId}</code>
          </p>
          {prior.length > 0 && (
            <label className="brief-history-select">
              Compare with{" "}
              <select
                value={selected ? versionKey(selected) : ""}
                onChange={(event) => setSelection(event.target.value)}
              >
                {prior.map((version) => (
                  <option value={versionKey(version)} key={versionKey(version)}>
                    Version {version.brief_version} · {version.run_id} ·{" "}
                    {version.created_at}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="brief-history-columns">
            <VersionCard
              version={selected}
              clientId={client.header.client_id}
              title="Earlier Meeting Brief"
              other={current}
              compare={true}
            />
            <VersionCard
              version={current}
              clientId={client.header.client_id}
              title="Current Meeting Brief"
              other={selected}
              compare={true}
            />
          </div>
          <p className="brief-history-reset-note">
            Highlighted claims have different wording or are absent in the other
            version. Evidence IDs identify each saved claim's sources;
            historical source contents are not reconstructed from today's
            records.
          </p>
        </>
      )}
    </section>
  );
}
