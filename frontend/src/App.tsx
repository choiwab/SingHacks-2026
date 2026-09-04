import { FluentProvider, teamsLightTheme } from "@fluentui/react-components";
import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { getMondayBrief } from "./api";
import { AppShell } from "./Shell";
import { EvidenceProvider } from "./evidence";
import type { MondayBriefProjection } from "./contracts";
import { MondayList } from "./MondayList";
import { PreRead } from "./PreRead";
import { Scenario } from "./Scenario";

function useRoute(projection: MondayBriefProjection) {
  const { pathname } = useLocation();
  const route = pathname.endsWith("/scenario")
    ? "scenario"
    : pathname.endsWith("/pre-read")
      ? "pre-read"
      : "list";
  const clientId = pathname.match(/^\/clients\/([^/]+)\//)?.[1];
  const selectedClient =
    clientId && projection.pre_reads[clientId] ? clientId : null;

  useEffect(() => {
    const titles = {
      list: "Monday list",
      "pre-read": "Pre-read",
      scenario: "Scenario rehearsal",
    };
    document.title = `${titles[route]} | Wealth Intelligence`;
    document.getElementById("main")?.scrollTo({ top: 0, behavior: "auto" });
  }, [pathname, route]);

  return { route, selectedClient } as const;
}

function RoutedApp({ projection }: { projection: MondayBriefProjection }) {
  const { route, selectedClient } = useRoute(projection);

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
          <Route path="/" element={<MondayList projection={projection} />} />
          <Route
            path="/clients/:clientId/pre-read"
            element={<PreRead projection={projection} />}
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
                  notice: "That page was not found. Showing the Monday list.",
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
              : "The projection could not be loaded.",
          );
      });
    return () => {
      active = false;
    };
  }, [attempt]);

  const status = useMemo(() => {
    if (!error) return <p role="status">Preparing the Monday list…</p>;
    return (
      <div role="alert">
        <p>{error}</p>
        <button
          type="button"
          onClick={() => {
            setError("");
            setAttempt((value) => value + 1);
          }}
        >
          Try again
        </button>
      </div>
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
