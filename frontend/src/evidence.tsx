import {
  Badge,
  Body1,
  Body1Strong,
  Button,
  Caption1,
  DrawerBody,
  DrawerHeader,
  DrawerHeaderTitle,
  OverlayDrawer,
  Subtitle2,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import { DismissRegular } from "@fluentui/react-icons";
import {
  createContext,
  useCallback,
  useContext,
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

/** Review state of a generated claim, as PRD 5.7 asks the drawer to show it. */
export type Authorship = "Unreviewed" | "Approved" | "Edited" | "Rejected";

interface EvidenceRequest {
  citations: CitationId[];
  clientId: string;
  claim?: string;
  authorship?: Authorship;
}

interface EvidenceControls {
  openEvidence: (request: EvidenceRequest) => void;
}

type ExpandedEvidence =
  | { type: "fact"; value: ProjectionFact }
  | { type: "evidence"; value: MondayBriefProjection["evidence"][string] };

const AUTHORSHIP: Record<
  Authorship,
  { label: string; color: "warning" | "success" | "brand" | "danger" }
> = {
  Unreviewed: { label: "Generated · awaiting RM review", color: "warning" },
  Approved: { label: "Approved by the RM", color: "success" },
  Edited: { label: "Edited by the RM", color: "brand" },
  Rejected: { label: "Rejected by the RM", color: "danger" },
};

const EvidenceContext = createContext<EvidenceControls | null>(null);

const useStyles = makeStyles({
  body: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalL,
  },
  claim: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    rowGap: tokens.spacingVerticalXS,
    ...shorthands.padding(tokens.spacingVerticalM, tokens.spacingHorizontalM),
    ...shorthands.borderRadius(tokens.borderRadiusMedium),
    backgroundColor: tokens.colorNeutralBackground3,
  },
  record: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    rowGap: tokens.spacingVerticalXS,
    ...shorthands.padding(tokens.spacingVerticalM, tokens.spacingHorizontalM),
    ...shorthands.borderRadius(tokens.borderRadiusMedium),
    border: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  factRecord: {
    backgroundColor: tokens.colorNeutralBackground1,
    borderTopColor: tokens.colorBrandStroke1,
    borderTopWidth: tokens.strokeWidthThicker,
  },
  fields: {
    display: "grid",
    gridTemplateColumns: "minmax(6rem, 0.4fr) 1fr",
    columnGap: tokens.spacingHorizontalM,
    rowGap: tokens.spacingVerticalXXS,
    width: "100%",
    ...shorthands.margin(0),
  },
  term: {
    ...shorthands.margin(0),
    color: tokens.colorNeutralForeground3,
    fontSize: tokens.fontSizeBase200,
    textTransform: "capitalize",
  },
  value: {
    ...shorthands.margin(0),
    fontSize: tokens.fontSizeBase200,
    fontVariantNumeric: "tabular-nums",
    overflowWrap: "anywhere",
  },
});

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

function formatValue(value: unknown) {
  if (value === null || value === undefined) return "Not recorded";
  if (typeof value === "number")
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return String(value);
}

function Fields({ record }: { record: Record<string, unknown> }) {
  const styles = useStyles();
  return (
    <dl className={styles.fields}>
      {Object.entries(record).map(([key, value]) => (
        <div key={key} style={{ display: "contents" }}>
          <dt className={styles.term}>{key.replaceAll("_", " ")}</dt>
          <dd className={styles.value}>{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function EvidenceItem({
  item,
  asOf,
}: {
  item: ExpandedEvidence;
  asOf: string;
}) {
  const styles = useStyles();

  if (item.type === "fact") {
    const fact = item.value;
    return (
      <article className={`${styles.record} ${styles.factRecord}`}>
        <Badge appearance="filled" color="brand">
          Deterministic fact
        </Badge>
        <Subtitle2 as="h3">{fact.what}</Subtitle2>
        <Caption1>Calculation inputs and result</Caption1>
        <Fields record={fact.numbers} />
        <Caption1>
          Confidence {fact.confidence} · as of {asOf} · fact {fact.id}
        </Caption1>
      </article>
    );
  }

  const evidence = item.value;
  return (
    <article className={styles.record}>
      <Badge appearance="outline" color="informative">
        {evidence.kind || "Source row"}
      </Badge>
      <Body1Strong>{evidence.title}</Body1Strong>
      <Caption1>
        {evidence.source} · row {evidence.id}
      </Caption1>
      <Fields record={evidence.record} />
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
  const styles = useStyles();
  const [request, setRequest] = useState<EvidenceRequest | null>(null);
  // Tabster does not restore focus for a drawer opened without a DialogTrigger,
  // so the "Why?" button that opened the trail is refocused on close.
  const trigger = useRef<HTMLElement | null>(null);
  const controls = useMemo<EvidenceControls>(
    () => ({
      openEvidence: (next) => {
        trigger.current = document.activeElement as HTMLElement | null;
        setRequest(next);
      },
    }),
    [],
  );
  const close = useCallback(() => {
    setRequest(null);
    trigger.current?.focus();
  }, []);
  const records = request
    ? expandCitations(projection, request.clientId, request.citations)
    : [];
  const authorship = request?.authorship && AUTHORSHIP[request.authorship];

  return (
    <EvidenceContext.Provider value={controls}>
      {children}
      <OverlayDrawer
        aria-label="Why?"
        position="end"
        size="medium"
        open={Boolean(request)}
        onOpenChange={(_, data) => {
          if (!data.open) close();
        }}
      >
        <DrawerHeader>
          <DrawerHeaderTitle
            action={
              <Button
                appearance="subtle"
                aria-label="Close source trail"
                icon={<DismissRegular />}
                onClick={close}
              />
            }
          >
            Why?
          </DrawerHeaderTitle>
          <Caption1>
            Cited facts, holdings, events, market inputs, and note rows appear
            below.
          </Caption1>
        </DrawerHeader>
        <DrawerBody className={styles.body}>
          {request?.claim && (
            <section className={styles.claim} aria-label="Generated claim">
              <Caption1>The claim on the dashboard</Caption1>
              <Body1>{request.claim}</Body1>
              {authorship && (
                <Badge appearance="tint" color={authorship.color}>
                  {authorship.label}
                </Badge>
              )}
            </section>
          )}
          {records.length > 0 ? (
            records.map((item) => (
              <EvidenceItem
                key={`${item.type}:${item.value.id}`}
                item={item}
                asOf={projection.as_of}
              />
            ))
          ) : (
            <Body1>No source row is attached to this line.</Body1>
          )}
        </DrawerBody>
      </OverlayDrawer>
    </EvidenceContext.Provider>
  );
}

export function useEvidence(): EvidenceControls {
  const controls = useContext(EvidenceContext);
  if (!controls)
    throw new Error("useEvidence must be used within EvidenceProvider");
  return controls;
}
