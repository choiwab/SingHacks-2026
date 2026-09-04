import { useEffect, useMemo, useRef, useState } from "react";
import {
  Badge,
  Body1Strong,
  Caption1,
  SearchBox,
  Tab,
  TabList,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import {
  CalendarLtr24Filled,
  CalendarLtr24Regular,
  DataTrending24Filled,
  DataTrending24Regular,
  DocumentBulletList24Filled,
  DocumentBulletList24Regular,
  bundleIcon,
} from "@fluentui/react-icons";
import { useNavigate } from "react-router-dom";

import type { MondayBriefProjection, RankedClient } from "./contracts";

const CalendarIcon = bundleIcon(CalendarLtr24Filled, CalendarLtr24Regular);
const PreReadIcon = bundleIcon(
  DocumentBulletList24Filled,
  DocumentBulletList24Regular,
);
const ScenarioIcon = bundleIcon(DataTrending24Filled, DataTrending24Regular);

/** Attention state shown next to each client in the switcher. */
const URGENCY: Record<
  RankedClient["urgency"],
  { label: string; color: "danger" | "warning" | "informative" }
> = {
  now: { label: "Act now", color: "danger" },
  soon: { label: "Prepare", color: "warning" },
  watch: { label: "Watch", color: "informative" },
};

const NARROW = "@media (max-width: 60rem)";

const useStyles = makeStyles({
  shell: {
    display: "grid",
    gridTemplateAreas: '"rail switcher main"',
    gridTemplateColumns: "auto auto minmax(0, 1fr)",
    // The single row must be allowed to shrink below its content, otherwise the
    // tall client list stretches the row past 100vh and the shell clips the
    // bottom of both panes instead of letting them scroll.
    gridTemplateRows: "minmax(0, 1fr)",
    height: "100vh",
    overflowY: "hidden",
    backgroundColor: tokens.colorNeutralBackground3,
    // Narrow windows keep the rail but lay the switcher out as a strip above
    // the dashboard so the main pane keeps a usable width.
    [NARROW]: {
      gridTemplateAreas: '"rail switcher" "rail main"',
      gridTemplateColumns: "auto minmax(0, 1fr)",
      gridTemplateRows: "auto minmax(0, 1fr)",
    },
  },
  rail: {
    gridArea: "rail",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    rowGap: tokens.spacingVerticalM,
    paddingBlock: tokens.spacingVerticalL,
    paddingInline: tokens.spacingHorizontalXS,
    backgroundColor: tokens.colorNeutralBackground3,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  brand: {
    width: "32px",
    height: "32px",
    display: "grid",
    placeItems: "center",
    marginBottom: tokens.spacingVerticalS,
    ...shorthands.borderRadius(tokens.borderRadiusMedium),
    backgroundColor: tokens.colorBrandBackground,
    color: tokens.colorNeutralForegroundOnBrand,
    fontWeight: tokens.fontWeightSemibold,
  },
  switcher: {
    gridArea: "switcher",
    display: "flex",
    flexDirection: "column",
    width: "17rem",
    paddingBlock: tokens.spacingVerticalL,
    paddingInline: tokens.spacingHorizontalM,
    rowGap: tokens.spacingVerticalS,
    backgroundColor: tokens.colorNeutralBackground2,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
    [NARROW]: {
      width: "auto",
      minWidth: 0,
      borderRight: "none",
      borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    },
  },
  switcherHead: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXXS,
  },
  list: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXXS,
    listStyleType: "none",
    ...shorthands.margin(0),
    ...shorthands.padding(0),
    // A flex item defaults to min-height:auto, which would size the list to all
    // 20 clients and defeat its own scrollbar.
    minHeight: 0,
    overflowY: "auto",
    [NARROW]: {
      flexDirection: "row",
      columnGap: tokens.spacingHorizontalXS,
      overflowX: "auto",
      overflowY: "hidden",
    },
  },
  clientButton: {
    display: "flex",
    flexDirection: "column",
    alignItems: "stretch",
    rowGap: "2px",
    width: "100%",
    textAlign: "left",
    cursor: "pointer",
    ...shorthands.border("none"),
    ...shorthands.borderRadius(tokens.borderRadiusMedium),
    paddingBlock: tokens.spacingVerticalS,
    paddingInline: tokens.spacingHorizontalM,
    backgroundColor: "transparent",
    ":hover": { backgroundColor: tokens.colorNeutralBackground3Hover },
    [NARROW]: { width: "15rem" },
  },
  clientSelected: {
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: tokens.shadow2,
  },
  clientTop: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    columnGap: tokens.spacingHorizontalS,
  },
  clientName: {
    minWidth: 0,
  },
  clientBadge: {
    flexShrink: 0,
    marginTop: "2px",
  },
  main: {
    gridArea: "main",
    minWidth: 0,
    overflowY: "auto",
    // Page layout responds to this pane, not the viewport, because the rail and
    // switcher take a fixed slice of the window.
    containerType: "inline-size",
    containerName: "main",
    backgroundColor: tokens.colorNeutralBackground1,
    ":focus-visible": {
      outlineStyle: "solid",
      outlineWidth: "2px",
      outlineColor: tokens.colorStrokeFocus2,
      outlineOffset: "-2px",
    },
  },
  empty: {
    paddingBlock: tokens.spacingVerticalM,
    color: tokens.colorNeutralForeground3,
  },
  rmContext: {
    display: "flex",
    flexDirection: "column",
    marginTop: "auto",
    paddingTop: tokens.spacingVerticalM,
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    color: tokens.colorNeutralForeground3,
    [NARROW]: { display: "none" },
  },
});

function ClientSwitcher({
  ranking,
  selectedClient,
  asOf,
}: {
  ranking: RankedClient[];
  selectedClient: string | null;
  asOf: string;
}) {
  const styles = useStyles();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const selectedButton = useRef<HTMLButtonElement>(null);

  const matches = useMemo(() => {
    const normalizeSearch = (value: string) =>
      value
        .toLowerCase()
        .replace(/[\p{Pd}\s]+/gu, " ")
        .trim();
    const needle = normalizeSearch(query);
    if (!needle) return ranking;
    const terms = needle.split(" ");
    return ranking.filter((client) => {
      const searchable = normalizeSearch(`${client.name} ${client.client_id}`);
      return terms.every((term) => searchable.includes(term));
    });
  }, [ranking, query]);

  useEffect(() => {
    selectedButton.current?.scrollIntoView({
      block: "nearest",
      inline: "nearest",
      behavior: "instant",
    });
  }, [selectedClient, matches]);

  return (
    <nav className={styles.switcher} aria-label="Client switcher">
      <div className={styles.switcherHead}>
        <Body1Strong>Clients</Body1Strong>
        <Caption1 role="status" aria-atomic="true">
          {query.trim()
            ? `${matches.length} of ${ranking.length} clients shown`
            : `${ranking.length} clients, ranked by priority`}
        </Caption1>
      </div>
      <SearchBox
        placeholder="Search by name or ID"
        aria-label="Search clients"
        value={query}
        onChange={(_, data) => setQuery(data.value)}
      />
      <ul className={styles.list}>
        {matches.map((client) => {
          const urgency = URGENCY[client.urgency];
          const selected = client.client_id === selectedClient;
          return (
            <li key={client.client_id}>
              <button
                ref={selected ? selectedButton : undefined}
                type="button"
                aria-current={selected ? "true" : undefined}
                className={`${styles.clientButton} ${selected ? styles.clientSelected : ""}`}
                onClick={() =>
                  navigate(`/clients/${client.client_id}/pre-read`)
                }
              >
                <span className={styles.clientTop}>
                  <Body1Strong className={styles.clientName}>
                    {client.name}
                  </Body1Strong>
                  <Badge
                    className={styles.clientBadge}
                    appearance="filled"
                    color={urgency.color}
                    size="small"
                  >
                    {urgency.label}
                  </Badge>
                </span>
                <Caption1>{client.meeting ?? "No meeting booked"}</Caption1>
              </button>
            </li>
          );
        })}
        {matches.length === 0 && (
          <li className={styles.empty}>
            <Caption1>No match for “{query}”.</Caption1>
          </li>
        )}
      </ul>
      <div className={styles.rmContext}>
        <Caption1>Priscilla Ong · Asia desk</Caption1>
        <Caption1>Data as of {asOf}</Caption1>
      </div>
    </nav>
  );
}

export function AppShell({
  projection,
  selectedClient,
  route,
  children,
}: {
  projection: MondayBriefProjection;
  selectedClient: string | null;
  route: "list" | "pre-read" | "scenario";
  children: React.ReactNode;
}) {
  const styles = useStyles();
  const navigate = useNavigate();

  return (
    <div className={styles.shell}>
      <nav className={styles.rail} aria-label="Workspace navigation">
        <span className={styles.brand} aria-hidden="true">
          WI
        </span>
        <TabList
          aria-label="Workspace views"
          vertical
          size="large"
          selectedValue={route}
          onTabSelect={(_, data) => {
            if (data.value === "list") navigate("/");
            else if (selectedClient)
              navigate(`/clients/${selectedClient}/${String(data.value)}`);
          }}
        >
          <Tab
            value="list"
            icon={<CalendarIcon />}
            aria-label="RM dashboard"
            title="RM dashboard"
          />
          <Tab
            value="pre-read"
            icon={<PreReadIcon />}
            aria-label="Pre-read"
            title="Pre-read"
            disabled={!selectedClient}
          />
          <Tab
            value="scenario"
            icon={<ScenarioIcon />}
            aria-label="Scenario rehearsal"
            title="Scenario rehearsal"
            disabled={!selectedClient}
          />
        </TabList>
      </nav>
      <ClientSwitcher
        ranking={projection.ranking}
        selectedClient={selectedClient}
        asOf={projection.as_of}
      />
      <main id="main" tabIndex={-1} className={styles.main}>
        {children}
      </main>
    </div>
  );
}
