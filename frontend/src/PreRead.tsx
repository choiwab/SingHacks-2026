import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { saveReview } from "./api";
import type { MondayBriefProjection, ReviewAction } from "./contracts";
import { CitedList, WhyButton, WorkflowList } from "./shared";

type ReviewState = "Unreviewed" | "Approved" | "Edited" | "Rejected";

export function PreRead({ projection }: { projection: MondayBriefProjection }) {
  const { clientId = "" } = useParams();
  const navigate = useNavigate();
  const preRead = projection.pre_reads[clientId];
  const [editing, setEditing] = useState(false);
  const [editedOpening, setEditedOpening] = useState(
    preRead?.opening.text ?? "",
  );
  const [reviewState, setReviewState] = useState<ReviewState>("Unreviewed");
  const [receipt, setReceipt] = useState("");
  const [toast, setToast] = useState("");
  const [saving, setSaving] = useState(false);
  const editField = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  if (!preRead) {
    return (
      <Navigate
        to="/"
        replace
        state={{
          notice: `Client ${clientId || "requested"} was not found. Showing the Monday list.`,
        }}
      />
    );
  }

  const rank = projection.ranking.findIndex(
    (client) => client.client_id === clientId,
  );
  const rankedClient = projection.ranking[rank];
  const currentOpening =
    reviewState === "Edited" ? editedOpening.trim() : preRead.opening.text;

  const persistReview = async (action: ReviewAction) => {
    setSaving(true);
    try {
      const text = action === "Edit" ? editedOpening.trim() : currentOpening;
      const response = await saveReview({ client_id: clientId, action, text });
      if (action === "Edit") setEditing(false);
      const labels: Record<ReviewAction, ReviewState> = {
        Approve: "Approved",
        Edit: "Edited",
        Reject: "Rejected",
      };
      const label = labels[action];
      setReviewState(label);
      const time = new Date(response.review.timestamp).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
      setReceipt(`Review log · ${label} · ${time} · ${response.review.rm}`);
      setToast(`${label} for ${preRead.name}.`);
    } catch (error) {
      setToast(
        error instanceof Error
          ? error.message
          : "The review could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = () => {
    if (editing) {
      void persistReview("Edit");
      return;
    }
    setEditing(true);
    window.setTimeout(() => editField.current?.focus(), 0);
  };

  return (
    <section className="screen pre-read-screen" aria-labelledby="client-name">
      <div className="screen-kicker">
        <button
          className="back-link"
          type="button"
          onClick={() => navigate("/")}
        >
          ← Monday list
        </button>
        <p>
          Selected priority{" "}
          <strong>
            #{rank + 1} · score {rankedClient?.score ?? 0}
          </strong>
        </p>
      </div>

      <header className="client-heading">
        <div>
          <p className="eyebrow accent">
            Decision pre-read · {preRead.client_id}
          </p>
          <h1 id="client-name">{preRead.name}</h1>
        </div>
        <div className={`review-state is-${reviewState.toLowerCase()}`}>
          {reviewState}
        </div>
      </header>

      <div className="pre-read-ledger">
        <section
          className="brief-block changed-block"
          aria-labelledby="changed-title"
        >
          <div className="block-heading">
            <p>01</p>
            <h2 id="changed-title">What changed</h2>
          </div>
          <CitedList
            items={preRead.what_changed}
            clientId={clientId}
            className="change-list"
          />
        </section>

        <section className="brief-block gap-block" aria-labelledby="gap-title">
          <div className="block-heading">
            <p>02</p>
            <h2 id="gap-title">You said / Data says</h2>
          </div>
          <div className="gap-pair">
            <div>
              <span>You said</span>
              <p>“{preRead.gap.belief}”</p>
            </div>
            <div className="data-says">
              <span>Data says</span>
              <p>{preRead.gap.data}</p>
              <WhyButton
                citations={preRead.gap.citations}
                clientId={clientId}
                inverse
              />
            </div>
          </div>
        </section>

        <section
          className="brief-block rules-block"
          aria-labelledby="rules-title"
        >
          <div className="block-heading">
            <p>03</p>
            <h2 id="rules-title">Rules &amp; money</h2>
          </div>
          <CitedList
            items={preRead.rules_money}
            clientId={clientId}
            className="rule-list"
          />
        </section>

        <section
          className="brief-block opening-block"
          aria-labelledby="opening-title"
        >
          <div className="block-heading">
            <p>04</p>
            <h2 id="opening-title">Suggested opening</h2>
          </div>
          <p className="language">{preRead.language}</p>
          <blockquote>{currentOpening}</blockquote>
          <WhyButton
            citations={preRead.opening.citations}
            clientId={clientId}
            inverse
          />
        </section>

        <section
          className="brief-block unsure-block"
          aria-labelledby="unsure-title"
        >
          <div className="block-heading">
            <p>05</p>
            <h2 id="unsure-title">What we are not sure about</h2>
          </div>
          <p>{preRead.uncertainty.text}</p>
          <WhyButton
            citations={preRead.uncertainty.citations}
            clientId={clientId}
          />
        </section>
      </div>

      <section className="workflow-strip" aria-labelledby="workflow-title">
        <div>
          <p className="eyebrow">CRM · Gmail · Teams · Map · Notes</p>
          <h2 id="workflow-title">Where you left off</h2>
        </div>
        <WorkflowList items={preRead.workflow} clientId={clientId} />
      </section>

      {editing && (
        <div className="edit-panel">
          <label htmlFor="edited-opening">Edit the opening line</label>
          <textarea
            ref={editField}
            id="edited-opening"
            rows={4}
            value={editedOpening}
            onChange={(event) => setEditedOpening(event.target.value)}
          />
        </div>
      )}

      <footer className="review-bar">
        <div className="review-copy">
          <strong>RM checkpoint</strong>
          <span>Only this decision is written to the review log.</span>
        </div>
        <div className="review-actions">
          <button
            type="button"
            className="reject-button"
            disabled={saving}
            onClick={() => void persistReview("Reject")}
          >
            Reject
          </button>
          <button
            type="button"
            className="edit-button"
            disabled={saving}
            onClick={handleEdit}
          >
            {editing ? "Save edit" : "Edit"}
          </button>
          <button
            type="button"
            className="approve-button"
            disabled={saving}
            onClick={() => void persistReview("Approve")}
          >
            Approve pre-read
          </button>
        </div>
      </footer>
      <div className="next-step">
        {receipt && (
          <p className="review-receipt" role="status">
            {receipt}
          </p>
        )}
        <button
          className="scenario-link"
          type="button"
          onClick={() => navigate(`/clients/${clientId}/scenario`)}
        >
          Rehearse a Strait scenario →
        </button>
      </div>
      {toast && (
        <div className="toast" role="status" aria-live="polite">
          {toast}
        </div>
      )}
    </section>
  );
}
