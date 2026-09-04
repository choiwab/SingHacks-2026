import {
  Button,
  FluentProvider,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  MessageBarTitle,
  Spinner,
  teamsLightTheme,
} from "@fluentui/react-components";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useParams,
} from "react-router-dom";

import { getMondayBrief } from "./api";
import { AppShell } from "./Shell";
import { EvidenceProvider } from "./evidence";
import type { Authorship } from "./evidence";
import type { MondayBriefProjection } from "./contracts";
import { Home } from "./Home";
import { PreRead } from "./PreRead";
import { Scenario } from "./Scenario";

function useRoute(projection: MondayBriefProjection) {
  const { pathname } = useLocation();
  const previousPath = useRef(pathname);
  const route = pathname.endsWith("/scenario")
    ? "scenario"
    : pathname.endsWith("/pre-read")
      ? "pre-read"
      : "list";
  const clientId = pathname.match(/^\/clients\/([^/]+)\//)?.[1];
  const selectedClient =
    clientId && projection.pre_reads[clientId] ? clientId : null;
  const clientName = selectedClient
    ? projection.pre_reads[selectedClient].name
    : null;

  useEffect(() => {
    const titles = {
      list: "RM dashboard",
      "pre-read": "Pre-read",
      scenario: "Scenario rehearsal",
    };
    document.title = [clientName, titles[route], "Wealth Intelligence"]
      .filter(Boolean)
      .join(" | ");
  }, [clientName, route]);

  useEffect(() => {
    const main = document.getElementById("main");
    main?.scrollTo({ top: 0, behavior: "auto" });
    // Enter the new screen after navigation without stealing focus on load.
    if (previousPath.current !== pathname) main?.focus({ preventScroll: true });
    previousPath.current = pathname;
  }, [pathname]);

  return { route, selectedClient } as const;
}

/**
 * React Router keeps one PreRead instance alive across `:clientId` changes, so
 * the key remounts it and stops one client's edit, receipt, or open tab from
 * being shown under the next client's name.
 */
function PreReadRoute(props: {
  projection: MondayBriefProjection;
  reviews: Record<string, Authorship>;
  savedOpenings: Record<string, string>;
  onReviewed: (clientId: string, state: Authorship, text: string) => void;
}) {
  const { clientId = "" } = useParams();
  return <PreRead key={clientId} {...props} />;
}

function RoutedApp({ projection }: { projection: MondayBriefProjection }) {
  const { route, selectedClient } = useRoute(projection);
  // The RM's review decisions live above the routes so the compact calendar and
  // the dashboard header agree on which briefs are ready.
  const [reviews, setReviews] = useState<Record<string, Authorship>>({});
  const [savedOpenings, setSavedOpenings] = useState<Record<string, string>>(
    {},
  );

  return (
    <EvidenceProvider projection={projection}>
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <AppShell
        projection={projection}
        selectedClient={selectedClient}
        route={route}
      >
        <Routes>
          <Route
            path="/"
            element={<Home projection={projection} reviews={reviews} />}
          />
          <Route
            path="/clients/:clientId/pre-read"
            element={
              <PreReadRoute
                projection={projection}
                reviews={reviews}
                savedOpenings={savedOpenings}
                onReviewed={(clientId, state, text) => {
                  setReviews((current) => ({ ...current, [clientId]: state }));
                  setSavedOpenings((current) => ({
                    ...current,
                    [clientId]: text,
                  }));
                }}
              />
            }
          />
          <Route
            path="/clients/:clientId/scenario"
            element={<Scenario projection={projection} />}
          />
          <Route
            path="*"
            element={
              <Navigate
                to="/"
                replace
                state={{
                  notice: "Page not found. Showing the dashboard.",
                }}
              />
            }
          />
        </Routes>
      </AppShell>
    </EvidenceProvider>
  );
}

export function App() {
  const [projection, setProjection] = useState<MondayBriefProjection | null>(
    null,
  );
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    getMondayBrief()
      .then((data) => {
        if (active) setProjection(data);
      })
      .catch((reason: unknown) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not reach the server.",
          );
      });
    return () => {
      active = false;
    };
  }, [attempt]);

  const status = useMemo(() => {
    if (!error)
      return (
        <Spinner
          role="status"
          label="Loading the dashboard…"
          labelPosition="below"
        />
      );
    return (
      <MessageBar intent="error" role="alert" className="app-status-message">
        <MessageBarBody>
          <MessageBarTitle>The dashboard did not load.</MessageBarTitle>
          {error}
        </MessageBarBody>
        <MessageBarActions>
          <Button
            appearance="primary"
            onClick={() => {
              setError("");
              setAttempt((value) => value + 1);
            }}
          >
            Try again
          </Button>
        </MessageBarActions>
      </MessageBar>
    );
  }, [error]);

  return (
    <FluentProvider theme={teamsLightTheme} className="fluent-root">
      {projection ? (
        <RoutedApp projection={projection} />
      ) : (
        <main className="app-status">{status}</main>
      )}
    </FluentProvider>
  );
}
