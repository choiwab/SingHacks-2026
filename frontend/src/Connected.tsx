import {
  Badge,
  Body1,
  Body1Strong,
  Caption1,
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
    gridTemplateColumns: "minmax(0, 2fr) minmax(0, 3fr)",
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
  panelHead: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    columnGap: tokens.spacingHorizontalM,
  },
  list: {
    display: "flex",
    flexDirection: "column",
    margin: 0,
    padding: 0,
    listStyleType: "none",
  },
  dayLabel: {
    marginTop: tokens.spacingVerticalM,
  },
  // A row is one click target: the whole record opens the client's brief.
  row: {
    display: "flex",
    flexDirection: "column",
    alignItems: "stretch",
    rowGap: tokens.spacingVerticalXXS,
    width: "100%",
    textAlign: "start",
    cursor: "pointer",
    backgroundColor: "transparent",
    border: "none",
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    paddingBlock: tokens.spacingVerticalM,
    paddingInline: 0,
    transitionProperty: "background-color",
    transitionDuration: "180ms",
    transitionTimingFunction: "ease",
    ":hover": { backgroundColor: tokens.colorNeutralBackground2 },
  },
  meetingRow: {
    display: "grid",
    gridTemplateColumns: "3.5rem minmax(0, 1fr)",
    columnGap: tokens.spacingHorizontalM,
    alignItems: "baseline",
  },
  time: {
    fontVariantNumeric: "tabular-nums",
    color: tokens.colorBrandForeground1,
    fontWeight: 500,
  },
  meetingText: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXXS,
    minWidth: 0,
  },
  rowTop: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    columnGap: tokens.spacingHorizontalM,
  },
  title: {
    minWidth: 0,
    overflowWrap: "anywhere",
  },
  sourceTag: {
    flexShrink: 0,
  },
  meta: {
    color: tokens.colorNeutralForeground3,
  },
  snippet: {
    color: tokens.colorNeutralForeground2,
    overflowWrap: "anywhere",
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
  },
  empty: {
    color: tokens.colorNeutralForeground3,
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
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-SG", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("en-SG", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Singapore",
  });
}

/** Body without the connector header lines (Subject/From/Scheduled/Location). */
function bodyLines(text: string): string {
  return text
    .split("\n")
    .filter(
      (line) =>
        !/^(Subject|From|To|Meeting|Scheduled|Location):/.test(line.trim()),
    )
    .join(" ")
    .trim();
}

function recordTitle(record: CommunicationRecord): string {
  const firstLine = record.text.split("\n")[0] ?? "";
  if (record.source === "calendar")
    return firstLine.replace(/^Meeting:\s*/, "") || "Meeting";
  if (record.source === "notes") {
    const body = bodyLines(record.text);
    return body.length > 72 ? `${body.slice(0, 72).trimEnd()}…` : body;
  }
  return firstLine.replace(/^Subject:\s*/, "") || "Message";
}

function MeetingRow({
  record,
  open,
}: {
  record: CommunicationRecord;
  open: () => void;
}) {
  const styles = useStyles();
  return (
    <li>
      <button type="button" className={styles.row} onClick={open}>
        <span className={styles.meetingRow}>
          <Body1Strong className={styles.time}>
            {formatTime(record.scheduled_at)}
          </Body1Strong>
          <span className={styles.meetingText}>
            <Body1Strong className={styles.title}>
              {recordTitle(record)}
            </Body1Strong>
            <Caption1 className={styles.meta}>
              {record.client_name ?? record.client_id}
            </Caption1>
          </span>
        </span>
      </button>
    </li>
  );
}

function MessageRow({
  record,
  showSource,
  open,
}: {
  record: CommunicationRecord;
  showSource: boolean;
  open: () => void;
}) {
  const styles = useStyles();
  const snippet = bodyLines(record.text);
  return (
    <li>
      <button type="button" className={styles.row} onClick={open}>
        <span className={styles.rowTop}>
          <Body1Strong className={styles.title}>
            {recordTitle(record)}
          </Body1Strong>
          {showSource && (
            <Badge
              appearance="tint"
              color="informative"
              className={styles.sourceTag}
            >
              {SOURCE_LABEL[record.source] ?? record.source}
            </Badge>
          )}
        </span>
        <Caption1 className={styles.meta}>
          {formatDay(recordDate(record))} ·{" "}
          {record.client_name ?? record.client_id}
        </Caption1>
        {record.source !== "notes" && (
          <Body1 className={styles.snippet}>{snippet}</Body1>
        )}
      </button>
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
  const navigate = useNavigate();
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

  const days = useMemo(() => {
    const meetings = (records ?? [])
      .filter((record) => record.source === "calendar")
      .sort((a, b) =>
        (a.scheduled_at ?? a.occurred_at).localeCompare(
          b.scheduled_at ?? b.occurred_at,
        ),
      );
    const grouped = new Map<string, CommunicationRecord[]>();
    for (const meeting of meetings) {
      const day = recordDate(meeting);
      grouped.set(day, [...(grouped.get(day) ?? []), meeting]);
    }
    return [...grouped.entries()];
  }, [records]);

  const messages = useMemo(
    () =>
      (records ?? [])
        .filter((record) => record.source !== "calendar")
        .filter((record) => filter === "all" || record.source === filter)
        .sort((a, b) => b.occurred_at.localeCompare(a.occurred_at)),
    [records, filter],
  );
  const meetingCount = days.reduce((total, [, rows]) => total + rows.length, 0);

  const open = (record: CommunicationRecord) => () =>
    navigate(`/clients/${record.client_id}/pre-read`);

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
            <div className={styles.panelHead}>
              <Eyebrow>Calendar</Eyebrow>
              <Caption1 className={styles.meta}>
                {meetingCount} meeting{meetingCount === 1 ? "" : "s"}
              </Caption1>
            </div>
            {meetingCount === 0 && (
              <Body1 className={styles.empty}>
                No meetings in connected calendars.
              </Body1>
            )}
            {days.map(([day, rows]) => (
              <div key={day}>
                <Caption1 className={mergeClasses(styles.meta, styles.dayLabel)}>
                  {formatDay(day)}
                </Caption1>
                <ul className={styles.list}>
                  {rows.map((record) => (
                    <MeetingRow
                      key={record.id}
                      record={record}
                      open={open(record)}
                    />
                  ))}
                </ul>
              </div>
            ))}
          </section>
          <section
            className={mergeClasses(surfaces.surface, styles.panel)}
            aria-label="Inbox"
          >
            <div className={styles.panelHead}>
              <Eyebrow>Inbox</Eyebrow>
              <Caption1 className={styles.meta}>
                {messages.length} message{messages.length === 1 ? "" : "s"}
              </Caption1>
            </div>
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
              <Body1 className={styles.empty}>
                No messages for this filter.
              </Body1>
            )}
            <ul className={styles.list}>
              {messages.map((record) => (
                <MessageRow
                  key={record.id}
                  record={record}
                  showSource={filter === "all"}
                  open={open(record)}
                />
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}
