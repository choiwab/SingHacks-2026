import { useEvidence } from "./evidence";
import type { Authorship } from "./evidence";
import type { CitedText, CitationId, WorkflowContext } from "./contracts";

export function WhyButton({
  citations,
  clientId,
  claim,
  authorship,
  inverse = false,
  children = "Why?",
}: {
  citations: CitationId[];
  clientId: string;
  /** The generated line this button sits under, shown at the top of the drawer. */
  claim?: string;
  authorship?: Authorship;
  inverse?: boolean;
  children?: string;
}) {
  const { openEvidence } = useEvidence();

  return (
    <button
      className={`why-link${inverse ? " inverse" : ""}`}
      type="button"
      onClick={() => openEvidence({ citations, clientId, claim, authorship })}
    >
      {children}
    </button>
  );
}

export function CitedList({
  items,
  clientId,
  authorship,
  className = "",
}: {
  items: CitedText[];
  clientId: string;
  authorship?: Authorship;
  className?: string;
}) {
  return (
    <ul className={`cited-list ${className}`.trim()}>
      {items.map((item, index) => (
        <li key={`${item.text}:${index}`}>
          <p>{item.text}</p>
          <WhyButton
            citations={item.citations}
            clientId={clientId}
            claim={item.text}
            authorship={authorship}
          />
        </li>
      ))}
    </ul>
  );
}

export function WorkflowList({
  items,
  clientId,
}: {
  items: WorkflowContext[];
  clientId: string;
}) {
  return (
    <div className="workflow-items">
      {items.map((item) => (
        <article
          className="workflow-item"
          key={`${item.system}:${item.status}`}
        >
          <div>
            <strong>{item.system}</strong>
            <span>{item.status}</span>
          </div>
          {item.citations.length > 0 && (
            <WhyButton citations={item.citations} clientId={clientId} />
          )}
        </article>
      ))}
    </div>
  );
}
