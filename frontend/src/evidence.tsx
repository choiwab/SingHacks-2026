import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";

import type {
  CitationId,
  MondayBriefProjection,
  ProjectionFact,
} from "./contracts";

interface EvidenceRequest {
  citations: CitationId[];
  clientId: string;
  trigger: HTMLElement;
}

interface EvidenceControls {
  openEvidence: (
    citations: CitationId[],
    clientId: string,
    trigger: HTMLElement,
  ) => void;
}

type ExpandedEvidence =
  | { type: "fact"; value: ProjectionFact }
  | { type: "evidence"; value: MondayBriefProjection["evidence"][string] };

const EvidenceContext = createContext<EvidenceControls | null>(null);

function expandCitations(
  projection: MondayBriefProjection,
  clientId: string,
  citations: CitationId[],
): ExpandedEvidence[] {
  const facts = projection.facts[clientId] ?? [];
  const factMap = new Map(facts.map((fact) => [fact.id, fact]));
  const records: ExpandedEvidence[] = [];
  const queue = [...citations];
  const seen = new Set<string>();

  while (queue.length > 0) {
    const citation = queue.shift();
    if (!citation || seen.has(citation)) continue;
    seen.add(citation);

    const fact = factMap.get(citation);
    if (fact) {
      records.push({ type: "fact", value: fact });
      queue.push(...fact.source_rows, ...fact.event_ids);
      continue;
    }

    const evidence = projection.evidence[citation];
    if (evidence) records.push({ type: "evidence", value: evidence });
  }

  return records;
}

function EvidenceItem({ item }: { item: ExpandedEvidence }) {
  if (item.type === "fact") {
    return (
      <article className="evidence-record fact-record">
        <p className="record-type">Computed fact</p>
        <h3>{item.value.what}</h3>
        <p className="evidence-source">Confidence: {item.value.confidence}</p>
      </article>
    );
  }

  return (
    <article className="evidence-record">
      <p className="record-type">{item.value.kind || "Source row"}</p>
      <h3>{item.value.title}</h3>
      <p className="evidence-source">{item.value.source}</p>
      <dl>
        {Object.entries(item.value.record).map(([key, value]) => (
          <div key={key} style={{ display: "contents" }}>
            <dt>{key.replaceAll("_", " ")}</dt>
            <dd>{value === null ? "Not recorded" : String(value)}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

export function EvidenceProvider({
  projection,
  children,
}: {
  projection: MondayBriefProjection;
  children: ReactNode;
}) {
  const [request, setRequest] = useState<EvidenceRequest | null>(null);
  const closeButton = useRef<HTMLButtonElement>(null);

  const closeEvidence = useCallback(() => {
    request?.trigger.focus();
    setRequest(null);
  }, [request]);

  useEffect(() => {
    if (!request) return;
    closeButton.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeEvidence();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [closeEvidence, request]);

  const controls = useMemo<EvidenceControls>(
    () => ({
      openEvidence: (citations, clientId, trigger) =>
        setRequest({ citations, clientId, trigger }),
    }),
    [],
  );
  const records = request
    ? expandCitations(projection, request.clientId, request.citations)
    : [];

  return (
    <EvidenceContext.Provider value={controls}>
      {children}
      <button
        className="drawer-scrim"
        type="button"
        aria-label="Close source trail"
        hidden={!request}
        onClick={closeEvidence}
      />
      <aside
        className={`evidence-drawer${request ? " is-open" : ""}`}
        aria-labelledby="evidence-title"
        aria-hidden={!request}
        aria-modal={request ? "true" : undefined}
        role="dialog"
        inert={!request}
      >
        <header>
          <div>
            <p className="eyebrow accent">Exact source rows</p>
            <h2 id="evidence-title">Why?</h2>
          </div>
          <button
            ref={closeButton}
            className="close-drawer"
            type="button"
            aria-label="Close source trail"
            onClick={closeEvidence}
          >
            ×
          </button>
        </header>
        <p className="drawer-rule">
          Cited facts, holdings, events, market inputs, and note rows appear
          below.
        </p>
        <div>
          {records.length > 0 ? (
            records.map((item) => (
              <EvidenceItem key={`${item.type}:${item.value.id}`} item={item} />
            ))
          ) : (
            <p>No source row is attached to this line.</p>
          )}
        </div>
      </aside>
    </EvidenceContext.Provider>
  );
}

export function useEvidence(): EvidenceControls {
  const controls = useContext(EvidenceContext);
  if (!controls)
    throw new Error("useEvidence must be used within EvidenceProvider");
  return controls;
}
