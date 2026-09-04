import type { MouseEvent } from "react";

import { useEvidence } from "./evidence";
import type { CitedText, CitationId, WorkflowContext } from "./contracts";

export function WhyButton({
  citations,
  clientId,
  inverse = false,
  children = "Why?",
}: {
  citations: CitationId[];
  clientId: string;
  inverse?: boolean;
  children?: string;
}) {
  const { openEvidence } = useEvidence();
  const handleClick = (event: MouseEvent<HTMLButtonElement>) => {
    openEvidence(citations, clientId, event.currentTarget);
  };

  return (
    <button
      className={`why-link${inverse ? " inverse" : ""}`}
      type="button"
      onClick={handleClick}
    >
      {children}
    </button>
  );
}

export function CitedList({
  items,
  clientId,
  className = "",
}: {
  items: CitedText[];
  clientId: string;
  className?: string;
}) {
  return (
    <ul className={`cited-list ${className}`.trim()}>
      {items.map((item, index) => (
        <li key={`${item.text}:${index}`}>
          <p>{item.text}</p>
          <WhyButton citations={item.citations} clientId={clientId} />
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
