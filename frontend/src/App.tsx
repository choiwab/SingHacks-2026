import { useEffect, useMemo, useState } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { getMondayBrief } from "./api";
import { EvidenceProvider } from "./evidence";
import type { MondayBriefProjection } from "./contracts";
import { MondayList } from "./MondayList";
import { PreRead } from "./PreRead";
import { Scenario } from "./Scenario";

function Header({ projection }: { projection: MondayBriefProjection }) {
  const navigate = useNavigate();
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
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [pathname, route]);

  return (
    <header className="topbar">
      <button className="brand" type="button" onClick={() => navigate("/")}>
        Wealth Intelligence
      </button>
      <nav className="product-nav" aria-label="Three screen workflow">
        <button
          type="button"
          aria-current={route === "list" ? "page" : undefined}
          onClick={() => navigate("/")}
        >
          Monday list
        </button>
        <button
          type="button"
          disabled={!selectedClient}
          aria-current={route === "pre-read" ? "page" : undefined}
          onClick={() =>
            selectedClient && navigate(`/clients/${selectedClient}/pre-read`)
          }
        >
          Pre-read
        </button>
        <button
          type="button"
          disabled={!selectedClient}
          aria-current={route === "scenario" ? "page" : undefined}
          onClick={() =>
            selectedClient && navigate(`/clients/${selectedClient}/scenario`)
          }
        >
          Scenario
        </button>
      </nav>
      <p className="rm-context">
        Priscilla Ong · Asia desk · Data as of Wed 26 Aug 2026
      </p>
    </header>
  );
}

function RoutedApp({ projection }: { projection: MondayBriefProjection }) {
  return (
    <EvidenceProvider projection={projection}>
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <Header projection={projection} />
      <main id="main">
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
      </main>
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

  if (!projection) return <main className="app-status">{status}</main>;
  return <RoutedApp projection={projection} />;
}
