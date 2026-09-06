import { useEffect, useState } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router-dom";
import type { LeaderMetric, StatLeader } from "../../api/client";
import type { ShellContext } from "../../components/AppShell";
import { Card } from "../../components/Card";
import { teamAccent, teamLabel } from "../../teams";
import { METRIC_LABELS, METRIC_ORDER, QUALIFIER_UNIT, formatMetric } from "./metrics";
import { useLeaders } from "./useLeaders";

const CONTROL =
  "rounded-md border border-line bg-surface px-2 py-1 text-xs text-muted transition-colors hover:text-ink";

function isLeaderMetric(value: string | null): value is LeaderMetric {
  return value !== null && (METRIC_ORDER as string[]).includes(value);
}

export function LeadersView() {
  const { dark } = useOutletContext<ShellContext>();
  const [params, setParams] = useSearchParams();

  const rawMetric = params.get("metric");
  const metric: LeaderMetric = isLeaderMetric(rawMetric) ? rawMetric : "woba";
  const limit = clampNumber(params.get("limit"), 10, 1, 100);
  const minimumParam = params.get("minimum");
  const minimum = minimumParam !== null && minimumParam !== "" ? Number(minimumParam) : null;

  const { data, loading, error } = useLeaders({ metric, limit, minimum });

  // The qualifier is typed into a text field, so hold it locally and only push it
  // into the URL once typing settles — otherwise every keystroke is a request.
  const [qualifierDraft, setQualifierDraft] = useState(minimumParam ?? "");
  useEffect(() => setQualifierDraft(minimumParam ?? ""), [minimumParam, metric]);
  useEffect(() => {
    const current = params.get("minimum") ?? "";
    if (qualifierDraft === current) return;
    const timer = window.setTimeout(() => {
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          if (qualifierDraft === "") next.delete("minimum");
          else next.set("minimum", qualifierDraft);
          return next;
        },
        { replace: true },
      );
    }, 400);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qualifierDraft]);

  function update(key: string, value: string | null) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (value === null) next.delete(key);
        else next.set(key, value);
        return next;
      },
      { replace: true },
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3 rounded-md border border-line bg-surface px-3.5 py-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted">metric</span>
          <div className="flex gap-1">
            {METRIC_ORDER.map((name) => (
              <button
                key={name}
                onClick={() => update("metric", name)}
                aria-pressed={metric === name}
                className={`${CONTROL} ${
                  metric === name ? "border-ink bg-ink text-app hover:text-app" : ""
                }`}
              >
                {METRIC_LABELS[name]}
              </button>
            ))}
          </div>
        </div>

        <label className="flex flex-col gap-1 text-xs text-muted">
          min {QUALIFIER_UNIT[metric]}
          <input
            type="number"
            min={0}
            value={qualifierDraft}
            placeholder="default"
            onChange={(event) => setQualifierDraft(event.target.value)}
            className="w-24 rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink outline-none"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-muted">
          show
          <select
            value={limit}
            onChange={(event) => update("limit", event.target.value)}
            className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink outline-none"
          >
            {[5, 10, 25, 50].map((option) => (
              <option key={option} value={option}>
                top {option}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error ? (
        <Card className="px-4 py-5">
          <p className="text-[13px] text-ink">{error}</p>
          <p className="mt-1.5 text-xs text-muted">
            Run the ingestion, then set <span className="font-mono">BASEBALL_STATS_SOURCE</span> to{" "}
            <span className="font-mono">postgres</span> and restart the API.
          </p>
        </Card>
      ) : (
        <Card padded={false}>
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-3.5 py-2.5">
            <span className="text-sm font-medium text-ink">
              {METRIC_LABELS[metric]} leaders
            </span>
            <span className="text-xs text-faint">
              {data
                ? `${data.qualifier} · ${
                    data.direction === "lower_is_better" ? "lower is better" : "higher is better"
                  } · season ${data.season}`
                : "loading…"}
            </span>
          </div>
          <LeaderTable
            metric={metric}
            leaders={data?.leaders ?? []}
            loading={loading}
            dark={dark}
          />
        </Card>
      )}
    </div>
  );
}

type LeaderTableProps = {
  metric: LeaderMetric;
  leaders: StatLeader[];
  loading: boolean;
  dark: boolean;
};

function LeaderTable({ metric, leaders, loading, dark }: LeaderTableProps) {
  if (loading && leaders.length === 0) {
    return <p className="px-3.5 py-5 text-sm text-faint">Loading leaders…</p>;
  }
  if (leaders.length === 0) {
    return (
      <p className="px-3.5 py-5 text-sm text-faint">
        No player clears this qualifier. Try lowering the minimum.
      </p>
    );
  }

  return (
    <div className={`overflow-x-auto transition-opacity ${loading ? "opacity-50" : ""}`}>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-xs text-faint">
            <th className="px-3.5 py-2 text-right font-normal">#</th>
            <th className="px-2 py-2 text-left font-normal">player</th>
            <th className="px-2 py-2 text-left font-normal">team</th>
            <th className="px-2 py-2 text-right font-normal">{METRIC_LABELS[metric]}</th>
            <th className="px-3.5 py-2 text-right font-normal">{QUALIFIER_UNIT[metric]}</th>
          </tr>
        </thead>
        <tbody>
          {leaders.map((leader) => {
            const team = leader.team_id !== null && leader.team_id !== undefined
              ? teamLabel(leader.team_id)
              : null;
            const playingTime =
              QUALIFIER_UNIT[metric] === "PA" ? leader.plate_appearances : leader.innings_pitched;
            return (
              <tr key={leader.player_id} className="border-t border-line">
                <td className="px-3.5 py-2 text-right font-mono text-xs text-faint">
                  {leader.rank}
                </td>
                <td className="px-2 py-2">
                  <Link
                    to={`/explore/players/${leader.player_id}`}
                    className="text-ink underline-offset-2 hover:underline"
                  >
                    {leader.full_name}
                  </Link>
                </td>
                <td className="px-2 py-2">
                  {team ? (
                    <span className="flex items-center gap-1.5">
                      <span
                        className="inline-block h-2.5 w-1 rounded-sm"
                        style={{ background: teamAccent(leader.team_id as number, dark) }}
                        aria-hidden
                      />
                      <span className="text-xs text-muted">{team.abbr}</span>
                    </span>
                  ) : (
                    <span className="text-xs text-faint">—</span>
                  )}
                </td>
                <td className="px-2 py-2 text-right font-mono font-medium text-ink">
                  {formatMetric(metric, leader.value)}
                </td>
                <td className="px-3.5 py-2 text-right font-mono text-xs text-muted">
                  {playingTime ?? "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function clampNumber(raw: string | null, fallback: number, low: number, high: number): number {
  const value = Number(raw);
  if (raw === null || !Number.isFinite(value)) return fallback;
  return Math.min(Math.max(Math.floor(value), low), high);
}
