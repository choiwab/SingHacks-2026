import {
  Body1,
  Button,
  Caption1,
  Field,
  Link,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  MessageBarTitle,
  Spinner,
  Subtitle1,
  Subtitle2,
  Tab,
  TabList,
  Textarea,
  makeStyles,
  mergeClasses,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import { DismissRegular } from "@fluentui/react-icons";
import { useEffect, useId, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { saveReview } from "./api";
import {
  CompactCalendar,
  DashboardHeader,
  DataPanel,
  DiscussionTopics,
  InsightsPanel,
  MemoryPanel,
  OpenCommitments,
  TopInsights,
  TwoMinuteSummary,
} from "./ClientDashboard";
import type { MondayBriefProjection, ReviewAction } from "./contracts";
import type { Authorship } from "./evidence";
import { CitedList, WhyButton, WorkflowList } from "./shared";

/** Lower-dashboard tabs required by PRD 5.6. */
const TABS = [
  { value: "overview", label: "Overview" },
  { value: "insights", label: "Insights" },
  { value: "data", label: "Data" },
  { value: "memory", label: "Memory" },
] as const;

type TabValue = (typeof TABS)[number]["value"];

const useStyles = makeStyles({
  tabPanel: {
    ":focus-visible": {
      outline: `2px solid ${tokens.colorStrokeFocus2}`,
      outlineOffset: "2px",
    },
  },
  brief: {
    display: "grid",
    rowGap: tokens.spacingVerticalXL,
    paddingBlock: tokens.spacingVerticalXL,
  },
  section: {
    display: "grid",
    rowGap: tokens.spacingVerticalM,
  },
  panel: {
    display: "grid",
    rowGap: tokens.spacingVerticalS,
    ...shorthands.padding(tokens.spacingVerticalL, tokens.spacingHorizontalL),
    ...shorthands.borderRadius(tokens.borderRadiusMedium),
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  /** "You said" beside "Data says" once there is room for two columns. */
  gapPair: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(18rem, 1fr))",
    gap: tokens.spacingHorizontalM,
  },
  dataSays: {
    backgroundColor: tokens.colorStatusDangerBackground1,
    ...shorthands.borderColor(tokens.colorStatusDangerBorder1),
  },
  dataSaysText: {
    color: tokens.colorStatusDangerForeground1,
  },
  label: {
    color: tokens.colorNeutralForeground3,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  quote: {
    maxWidth: "44ch",
    ...shorthands.margin(0),
  },
  prose: {
    maxWidth: "60ch",
  },
  actions: {
    display: "flex",
    justifyContent: "flex-start",
  },
});

/**
 * One block of the meeting brief (PRD 5.5). The section carries its own
 * accessible name so each block is a landmark the RM can jump between.
 */
function BriefSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const styles = useStyles();

  return (
    <section className={styles.section} aria-label={title}>
      <Subtitle1 as="h2">{title}</Subtitle1>
      {children}
    </section>
  );
}

export function PreRead({
  projection,
  reviews,
  savedOpenings,
  onReviewed,
}: {
  projection: MondayBriefProjection;
  reviews: Record<string, Authorship>;
  savedOpenings: Record<string, string>;
  onReviewed: (clientId: string, state: Authorship, text: string) => void;
}) {
  const styles = useStyles();
  const { clientId = "" } = useParams();
  const navigate = useNavigate();
  const preRead = projection.pre_reads[clientId];
  const [editing, setEditing] = useState(false);
  const [editedOpening, setEditedOpening] = useState(
    savedOpenings[clientId] ?? preRead?.opening.text ?? "",
  );
  const [receipt, setReceipt] = useState("");
  const [toast, setToast] = useState("");
  // A failed review is kept until the RM dismisses it; only the confirmation
  // is allowed to disappear on its own.
  const [reviewError, setReviewError] = useState<{
    message: string;
    action: ReviewAction;
  } | null>(null);
  const [emptyOpening, setEmptyOpening] = useState(false);
  const [pending, setPending] = useState<ReviewAction | null>(null);
  const [tab, setTab] = useState<TabValue>("overview");
  const [memoryQuery, setMemoryQuery] = useState("");
  const panelId = useId();
  const reviewState = reviews[clientId] ?? "Unreviewed";
  const editField = useRef<HTMLTextAreaElement>(null);
  const editPanel = useRef<HTMLDivElement>(null);
  const editButton = useRef<HTMLButtonElement>(null);
  const approveButton = useRef<HTMLButtonElement>(null);
  const rejectButton = useRef<HTMLButtonElement>(null);
  const reviewBar = useRef<HTMLElement>(null);
  const briefPanel = useRef<HTMLDivElement>(null);

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
          notice: `Client ${clientId || "requested"} was not found. Showing the dashboard.`,
        }}
      />
    );
  }

  const rank = projection.ranking.findIndex(
    (client) => client.client_id === clientId,
  );
  const rankedClient = projection.ranking[rank];
  const facts = projection.facts[clientId] ?? [];
  const currentOpening = savedOpenings[clientId] ?? preRead.opening.text;

  const persistReview = async (action: ReviewAction) => {
    if (action === "Edit" && !editedOpening.trim()) {
      setEmptyOpening(true);
      editField.current?.focus();
      return;
    }
    setPending(action);
    setReviewError(null);
    try {
      const text = action === "Edit" ? editedOpening.trim() : currentOpening;
      const response = await saveReview({ client_id: clientId, action, text });
      if (action === "Edit") {
        const restoreFocus = editPanel.current?.contains(
          document.activeElement,
        );
        flushSync(() => setEditing(false));
        if (restoreFocus) editButton.current?.focus();
      }
      const labels: Record<ReviewAction, Authorship> = {
        Approve: "Approved",
        Edit: "Edited",
        Reject: "Rejected",
      };
      const label = labels[action];
      onReviewed(clientId, label, response.review.text);
      const time = new Date(response.review.timestamp).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
      setReceipt(`Review log · ${label} · ${time} · ${response.review.rm}`);
      setToast(`${label} for ${preRead.name}.`);
    } catch (error) {
      setReviewError({
        message:
          error instanceof Error
            ? error.message
            : "The review could not be saved.",
        action,
      });
    } finally {
      setPending(null);
    }
  };

  const handleEdit = () => {
    if (editing) {
      void persistReview("Edit");
      return;
    }
    setEditedOpening(currentOpening);
    setEditing(true);
    window.setTimeout(() => editField.current?.focus(), 0);
  };

  return (
    <section className="screen pre-read-screen" aria-labelledby="client-name">
      <div className="screen-kicker">
        <Link as="button" type="button" onClick={() => navigate("/")}>
          ← RM dashboard
        </Link>
        <p>
          <strong>
            Priority #{rank + 1} · score {rankedClient?.score ?? 0}
          </strong>
        </p>
      </div>

      <CompactCalendar
        projection={projection}
        reviews={reviews}
        selectedClient={clientId}
        onOpenSelectedBrief={() => {
          flushSync(() => setTab("overview"));
          briefPanel.current?.focus({ preventScroll: true });
          briefPanel.current?.scrollIntoView({ block: "start" });
        }}
      />

      <div className="client-heading">
        <DashboardHeader
          preRead={preRead}
          ranked={rankedClient}
          facts={facts}
          asOf={projection.as_of}
          reviewState={reviewState}
          onReviewBrief={() => {
            // Commit the longer brief before measuring the checkpoint position.
            flushSync(() => setTab("overview"));
            reviewBar.current?.focus({ preventScroll: true });
            reviewBar.current?.scrollIntoView({ block: "center" });
          }}
        />
      </div>

      <TopInsights preRead={preRead} facts={facts} />

      <TabList
        className="dashboard-tabs"
        aria-label="Client intelligence"
        selectedValue={tab}
        onTabSelect={(_, data) => setTab(data.value as TabValue)}
      >
        {TABS.map((item) => (
          <Tab
            key={item.value}
            id={`tab-${item.value}`}
            value={item.value}
            aria-controls={panelId}
          >
            {item.label}
          </Tab>
        ))}
      </TabList>

      <div
        id={panelId}
        ref={briefPanel}
        className={styles.tabPanel}
        role="tabpanel"
        aria-labelledby={`tab-${tab}`}
        tabIndex={0}
      >
        {tab === "insights" && (
          <InsightsPanel
            preRead={{
              ...preRead,
              opening: { ...preRead.opening, text: currentOpening },
            }}
            facts={facts}
            authorship={reviewState}
          />
        )}
        {tab === "data" && <DataPanel facts={facts} clientId={clientId} />}
        {tab === "memory" && (
          <MemoryPanel
            preRead={preRead}
            evidence={projection.evidence}
            query={memoryQuery}
            onQueryChange={setMemoryQuery}
          />
        )}
        {tab === "overview" && (
          <div className={styles.brief}>
            <BriefSection title="Two-minute summary">
              <TwoMinuteSummary
                preRead={preRead}
                ranked={rankedClient}
                facts={facts}
                authorship={reviewState}
              />
            </BriefSection>

            <BriefSection title="Three discussion topics">
              <DiscussionTopics facts={facts} clientId={clientId} />
            </BriefSection>

            <BriefSection title="What changed">
              <CitedList
                items={preRead.what_changed}
                clientId={clientId}
                authorship={reviewState}
              />
            </BriefSection>

            <BriefSection title="You said / Data says">
              <div className={styles.gapPair}>
                <div className={styles.panel}>
                  <Caption1 className={styles.label}>You said</Caption1>
                  <Subtitle2 as="p" className={styles.quote}>
                    “{preRead.gap.belief}”
                  </Subtitle2>
                </div>
                <div className={mergeClasses(styles.panel, styles.dataSays)}>
                  <Caption1 className={styles.label}>Data says</Caption1>
                  <Subtitle2
                    as="p"
                    className={mergeClasses(styles.quote, styles.dataSaysText)}
                  >
                    {preRead.gap.data}
                  </Subtitle2>
                  <div className={styles.actions}>
                    <WhyButton
                      citations={preRead.gap.citations}
                      clientId={clientId}
                      claim={`${preRead.name} · You said: “${preRead.gap.belief}” Data says: ${preRead.gap.data}`}
                      authorship={reviewState}
                    />
                  </div>
                </div>
              </div>
            </BriefSection>

            <BriefSection title="Rules & money">
              <CitedList
                items={preRead.rules_money}
                clientId={clientId}
                authorship={reviewState}
              />
            </BriefSection>

            <BriefSection title="Open commitments">
              <OpenCommitments
                facts={facts}
                evidence={projection.evidence}
                clientId={clientId}
              />
            </BriefSection>

            <BriefSection title="Suggested opening">
              <div className={styles.panel}>
                <Caption1 className={styles.label}>{preRead.language}</Caption1>
                <Subtitle2 as="p" className={styles.quote}>
                  {currentOpening}
                </Subtitle2>
                <div className={styles.actions}>
                  <WhyButton
                    citations={preRead.opening.citations}
                    clientId={clientId}
                    claim={currentOpening}
                    authorship={reviewState}
                  />
                </div>
              </div>
            </BriefSection>

            <BriefSection title="What we are not sure about">
              <Body1 className={styles.prose}>{preRead.uncertainty.text}</Body1>
              <div className={styles.actions}>
                <WhyButton
                  citations={preRead.uncertainty.citations}
                  clientId={clientId}
                  claim={preRead.uncertainty.text}
                  authorship={reviewState}
                />
              </div>
            </BriefSection>

            <BriefSection title="Where you left off">
              <WorkflowList items={preRead.workflow} clientId={clientId} />
            </BriefSection>
          </div>
        )}
      </div>

      {editing && (
        <div className="edit-panel" ref={editPanel}>
          <Field
            label="Edit the opening line"
            hint="Saved to the review log as your wording."
            validationMessage={
              emptyOpening ? "Enter an opening line before saving." : undefined
            }
            validationState={emptyOpening ? "error" : "none"}
          >
            <Textarea
              ref={editField}
              id="edited-opening"
              resize="vertical"
              rows={4}
              readOnly={pending !== null}
              value={editedOpening}
              onChange={(_event, data) => {
                setEditedOpening(data.value);
                if (data.value.trim()) setEmptyOpening(false);
              }}
            />
          </Field>
          <Button
            disabledFocusable={pending !== null}
            onClick={() => {
              setEditedOpening(currentOpening);
              setEditing(false);
              setReviewError(null);
              setEmptyOpening(false);
              editButton.current?.focus();
            }}
          >
            Cancel edit
          </Button>
        </div>
      )}

      {reviewError && (
        <MessageBar intent="error" role="alert" className="review-error">
          <MessageBarBody>
            <MessageBarTitle>The review was not saved.</MessageBarTitle>
            {reviewError.message} The brief stays open.
          </MessageBarBody>
          <MessageBarActions
            containerAction={
              <Button
                appearance="transparent"
                icon={<DismissRegular />}
                aria-label="Dismiss the review error"
                onClick={() => {
                  const retryButton = {
                    Approve: approveButton,
                    Edit: editButton,
                    Reject: rejectButton,
                  }[reviewError.action];
                  flushSync(() => setReviewError(null));
                  retryButton.current?.focus();
                }}
              />
            }
          />
        </MessageBar>
      )}

      <footer
        className="review-bar"
        ref={reviewBar}
        role="region"
        aria-label="RM checkpoint"
        tabIndex={-1}
        aria-busy={pending !== null}
      >
        <div className="review-copy">
          <strong>RM checkpoint</strong>
          <span id="review-guidance">
            {editing
              ? "Save or cancel your edit before approving or rejecting."
              : "Only this decision is logged."}
          </span>
        </div>
        <div className="review-actions">
          <Button
            ref={rejectButton}
            disabledFocusable={editing || pending !== null}
            aria-describedby={editing ? "review-guidance" : undefined}
            icon={pending === "Reject" ? <Spinner size="tiny" /> : undefined}
            onClick={() => void persistReview("Reject")}
          >
            Reject
          </Button>
          <Button
            disabledFocusable={pending !== null}
            icon={pending === "Edit" ? <Spinner size="tiny" /> : undefined}
            ref={editButton}
            onClick={handleEdit}
          >
            {editing ? "Save edit" : "Edit"}
          </Button>
          <Button
            ref={approveButton}
            appearance="primary"
            className="approve-button"
            disabledFocusable={editing || pending !== null}
            aria-describedby={editing ? "review-guidance" : undefined}
            icon={pending === "Approve" ? <Spinner size="tiny" /> : undefined}
            onClick={() => void persistReview("Approve")}
          >
            Approve pre-read
          </Button>
        </div>
      </footer>
      <div className="next-step">
        {receipt && (
          <p className="review-receipt" role="status">
            {receipt}
          </p>
        )}
        <Link
          as="button"
          type="button"
          onClick={() => navigate(`/clients/${clientId}/scenario`)}
        >
          Rehearse a Strait scenario →
        </Link>
      </div>
      {toast && (
        <div className="toast" role="status" aria-live="polite">
          {toast}
        </div>
      )}
    </section>
  );
}
