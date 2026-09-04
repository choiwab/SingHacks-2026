import { useLocation, useNavigate } from "react-router-dom";

import type { MondayBriefProjection, RankedClient } from "./generated/api";

const WEEK = [
  { key: "Mon", label: "Mon", date: "31 Aug" },
  { key: "Tue", label: "Tue", date: "1 Sep" },
  { key: "Wed", label: "Wed", date: "2 Sep" },
  { key: "Thu", label: "Thu", date: "3 Sep" },
  { key: "Fri", label: "Fri", date: "4 Sep" },
] as const;

function PriorityMeta({
  client,
  rank,
}: {
  client: RankedClient;
  rank: number;
}) {
  return (
    <span className="priority-meta">
      <span className="priority-rank">#{rank + 1}</span>
      <span>{client.score.toFixed(0)}</span>
    </span>
  );
}

function CallRow({
  client,
  rank,
  open,
}: {
  client: RankedClient;
  rank: number;
  open: () => void;
}) {
  return (
    <button
      className={`call-row urgency-${client.urgency}`}
      type="button"
      onClick={open}
    >
      <PriorityMeta client={client} rank={rank} />
      <span className="client-copy">
        <strong className="client-name">{client.name}</strong>
        <span className="client-reason">{client.reason}</span>
      </span>
      <span className="row-action">Open →</span>
    </button>
  );
}

function MeetingCard({
  client,
  rank,
  open,
}: {
  client: RankedClient;
  rank: number;
  open: () => void;
}) {
  const time = client.meeting?.split(" ").slice(1).join(" ") ?? "";
  return (
    <button
      className={`meeting-card urgency-${client.urgency}`}
      type="button"
      onClick={open}
    >
      <span className="meeting-meta">
        <span>
          #{rank + 1} · {client.score}
        </span>
        <span>{time}</span>
      </span>
      <strong className="meeting-client">{client.name}</strong>
      <span className="meeting-reason">{client.reason}</span>
      <span className="meeting-action">Open pre-read →</span>
    </button>
  );
}

export function MondayList({
  projection,
}: {
  projection: MondayBriefProjection;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const routeState = location.state as { notice?: string } | null;
  const calls = projection.ranking.filter((client) => !client.meeting);
  const meetings = projection.ranking.filter((client) => client.meeting);
  const ranks = new Map(
    projection.ranking.map((client, index) => [client.client_id, index]),
  );
  const openClient = (clientId: string) =>
    navigate(`/clients/${clientId}/pre-read`);

  return (
    <section className="screen list-screen" aria-labelledby="list-title">
      {routeState?.notice && (
        <p className="route-notice" role="status">
          {routeState.notice}
        </p>
      )}
      <header className="calendar-hero">
        <div>
          <p className="eyebrow accent">31 Aug - 4 Sep 2026</p>
          <h1 id="list-title">Calls to make. Meetings to prepare.</h1>
        </div>
      </header>

      <div className="feature-intro">
        <p>
          <span>Feature 01</span> Explainable Priority Calendar
        </p>
        <div className="urgency-legend" aria-label="Urgency legend">
          <span>
            <i className="legend-fill" /> Act now
          </span>
          <span>
            <i className="legend-outline" /> Prepare next
          </span>
          <span>
            <i className="legend-watch" /> Watch
          </span>
        </div>
      </div>

      <div className="calendar-workspace">
        <aside className="call-rail" aria-labelledby="call-title">
          <header>
            <p className="eyebrow">No meeting booked</p>
            <h2 id="call-title">Call this week</h2>
            <p>{calls.length} clients ranked</p>
          </header>
          <div className="call-list" aria-live="polite">
            {calls.map((client) => (
              <CallRow
                key={client.client_id}
                client={client}
                rank={ranks.get(client.client_id) ?? 0}
                open={() => openClient(client.client_id)}
              />
            ))}
          </div>
        </aside>

        <section className="week-board" aria-labelledby="meeting-title">
          <header className="week-board-heading">
            <div>
              <p className="eyebrow">Booked meetings</p>
              <h2 id="meeting-title">Prepare before the call</h2>
            </div>
            <p>{meetings.length} meetings</p>
          </header>
          <div className="meeting-grid" aria-live="polite">
            {WEEK.map((day) => {
              const dayMeetings = meetings.filter((client) =>
                client.meeting?.startsWith(day.key),
              );
              return (
                <section
                  className={`day-column${dayMeetings.length === 0 ? " is-empty" : ""}`}
                  key={day.key}
                >
                  <header className="day-heading">
                    <span>{day.label}</span>
                    <strong>{day.date}</strong>
                  </header>
                  {dayMeetings.length > 0 ? (
                    dayMeetings.map((client) => (
                      <MeetingCard
                        key={client.client_id}
                        client={client}
                        rank={ranks.get(client.client_id) ?? 0}
                        open={() => openClient(client.client_id)}
                      />
                    ))
                  ) : (
                    <p className="open-day">Open for preparation</p>
                  )}
                </section>
              );
            })}
          </div>
        </section>
      </div>
    </section>
  );
}
