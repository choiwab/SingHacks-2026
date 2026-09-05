import {
  Badge,
  Body1,
  Body1Strong,
  Caption1,
  Link,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
  Spinner,
  Tab,
  TabList,
  makeStyles,
  mergeClasses,
  tokens,
} from "@fluentui/react-components";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getCommunications, isPreview } from "./api";
import type { CommunicationRecord } from "./live/adapter";
import { Eyebrow, useSurfaceStyles } from "./shared";

const useStyles = makeStyles({
  page: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXL,
    maxWidth: "var(--page)",
    marginInline: "auto",
    paddingBlock: tokens.spacingVerticalXXL,
    paddingInline: tokens.spacingHorizontalXXL,
  },
  heading: {
    fontSize: tokens.fontSizeHero800,
    lineHeight: tokens.lineHeightHero800,
    fontWeight: 300,
    letterSpacing: "-0.01em",
    margin: 0,
  },
  columns: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 5fr) minmax(0, 7fr)",
    columnGap: tokens.spacingHorizontalXL,
    rowGap: tokens.spacingVerticalXL,
    alignItems: "start",
    "@media (max-width: 60rem)": {
      gridTemplateColumns: "minmax(0, 1fr)",
    },
  },
  panel: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalM,
    paddingBlock: tokens.spacingVerticalL,
    paddingInline: tokens.spacingHorizontalL,
  },
  list: {
    display: "flex",
    flexDirection: "column",
    margin: 0,
    padding: 0,
    listStyleType: "none",
  },
  row: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXS,
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    paddingBlock: tokens.spacingVerticalM,
  },
  rowTop: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    columnGap: tokens.spacingHorizontalM,
    flexWrap: "wrap",
  },
  snippet: {
    color: tokens.colorNeutralForeground2,
    whiteSpace: "pre-line",
    overflowWrap: "anywhere",
  },
  meta: {
    color: tokens.colorNeutralForeground3,
  },
  dayLabel: {
    marginTop: tokens.spacingVerticalM,
  },
});

const SOURCE_LABEL: Record<string, string> = {
  gmail: "Gmail",
  outlook: "Outlook",
  calendar: "Calendar",
  notes: "RM note",
  teams: "Teams",
};

function recordDate(record: CommunicationRecord): string {
  return (record.scheduled_at ?? record.occurred_at).slice(0, 10);
}

function formatDay(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`);
  return date.toLocaleDateString("en-SG", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  return date.toLocaleTimeString("en-SG", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  });
}

function snippet(text: string, limit = 260): string {
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).trimEnd()}…`;
}

function RecordRow({ record }: { record: CommunicationRecord }) {
  const styles = useStyles();
  const navigate = useNavigate();
  const isMeeting = record.source === "calendar";
  const title = isMeeting
    ? (record.text.split("\n")[0] ?? "Meeting").replace(/^Meeting:\s*/, "")
    : (record.text.split("\n")[0] ?? "");
  return (
    <li className={styles.row}>
      <div className={styles.rowTop}>
        <Body1Strong>{title}</Body1Strong>
        <Badge appearance="tint" color={isMeeting ? "brand" : "informative"}>
          {SOURCE_LABEL[record.source] ?? record.source}
        </Badge>
      </div>
      <Caption1 className={styles.meta}>
        {formatDay(recordDate(record))}
        {isMeeting && record.scheduled_at
          ? ` · ${formatTime(record.scheduled_at)}`
          : ""}
        {" · "}
        <Link
          as="button"
          type="button"
          onClick={() => navigate(`/clients/${record.client_id}/pre-read`)}
        >
          {record.client_name ?? record.client_id}
        </Link>
        {record.participants.length > 0
          ? ` · ${record.participants.join(", ")}`
          : ""}
      </Caption1>
      {!isMeeting && <Body1 className={styles.snippet}>{snippet(record.text)}</Body1>}
      {isMeeting && (
        <Body1 className={styles.snippet}>
          {snippet(record.text.split("\n").slice(1).join("\n"))}
        </Body1>
      )}
    </li>
  );
}

/**
 * The connected-workspace surface: calendar events and messages pulled from
 * each client's durable agent memory (dataset notes plus connector snapshots).
 * Live backend only; the fixture preview has no connector store.
 */
export function Connected() {
  const styles = useStyles();
  const surfaces = useSurfaceStyles();
  const [records, setRecords] = useState<CommunicationRecord[] | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    if (isPreview) return;
    let active = true;
    getCommunications()
      .then((data) => {
        if (active) setRecords(data.records);
      })
      .catch((reason: unknown) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not load communications.",
          );
      });
    return () => {
      active = false;
    };
  }, []);

  const meetings = useMemo(
    () =>
      (records ?? [])
        .filter((record) => record.source === "calendar")
        .sort((a, b) =>
          (a.scheduled_at ?? a.occurred_at).localeCompare(
            b.scheduled_at ?? b.occurred_at,
          ),
        ),
    [records],
  );
  const messages = useMemo(
    () =>
      (records ?? [])
        .filter((record) => record.source !== "calendar")
        .filter((record) => filter === "all" || record.source === filter)
        .sort((a, b) => b.occurred_at.localeCompare(a.occurred_at)),
    [records, filter],
  );

  if (isPreview) {
    return (
      <div className={styles.page}>
        <MessageBar intent="info" role="note">
          <MessageBarBody>
            <MessageBarTitle>Connected sources are live-only.</MessageBarTitle>
            The fixture preview has no connector store. Run the live dashboard
            to see calendar and inbox data.
          </MessageBarBody>
        </MessageBar>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header>
        <Eyebrow>Connected sources</Eyebrow>
        <h1 className={styles.heading}>Calendar & inbox</h1>
        <Caption1 className={styles.meta}>
          From each client's agent memory: RM notes, mail, and meetings.
        </Caption1>
      </header>
      {error && (
        <MessageBar intent="error" role="alert">
          <MessageBarBody>
            <MessageBarTitle>Communications did not load.</MessageBarTitle>
            {error}
          </MessageBarBody>
        </MessageBar>
      )}
      {!records && !error && (
        <Spinner role="status" label="Loading communications…" />
      )}
      {records && (
        <div className={styles.columns}>
          <section
            className={mergeClasses(surfaces.surface, styles.panel)}
            aria-label="Upcoming meetings"
          >
            <Eyebrow>Calendar</Eyebrow>
            {meetings.length === 0 && (
              <Body1>No meetings in connected calendars.</Body1>
            )}
            <ul className={styles.list}>
              {meetings.map((record) => (
                <RecordRow key={record.id} record={record} />
              ))}
            </ul>
          </section>
          <section
            className={mergeClasses(surfaces.surface, styles.panel)}
            aria-label="Inbox"
          >
            <Eyebrow>Inbox</Eyebrow>
            <TabList
              selectedValue={filter}
              onTabSelect={(_, data) => setFilter(String(data.value))}
              aria-label="Filter messages by source"
            >
              <Tab value="all">All</Tab>
              <Tab value="gmail">Gmail</Tab>
              <Tab value="notes">RM notes</Tab>
            </TabList>
            {messages.length === 0 && (
              <Body1>No messages for this filter.</Body1>
            )}
            <ul className={styles.list}>
              {messages.map((record) => (
                <RecordRow key={record.id} record={record} />
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}
