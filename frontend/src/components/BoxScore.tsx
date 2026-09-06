import { useMemo } from "react";
import type { Play } from "../api/client";
import { teamLabel } from "../teams";

type BoxScoreProps = {
  plays: Play[];
  homeTeamId: number;
  awayTeamId: number;
  homeAccent: string;
  awayAccent: string;
};

type TeamTotals = { runs: number; hits: number; homeRuns: number; walks: number };

const HIT_EVENTS = new Set(["single", "double", "triple", "home_run"]);

export function BoxScore({ plays, homeTeamId, awayTeamId, homeAccent, awayAccent }: BoxScoreProps) {
  const { totals, stars } = useMemo(
    () => summarize(plays, homeTeamId),
    [plays, homeTeamId],
  );

  return (
    <div className="rounded-md border border-line bg-surface px-3.5 py-3">
      <div className="mb-2 text-xs font-medium text-muted">Box score</div>
      <table className="w-full border-collapse font-mono text-xs">
        <thead>
          <tr className="text-faint">
            <th className="py-1 text-left font-normal"></th>
            <th className="px-2 py-1 text-right font-normal">R</th>
            <th className="px-2 py-1 text-right font-normal">H</th>
            <th className="px-2 py-1 text-right font-normal">HR</th>
            <th className="px-2 py-1 text-right font-normal">BB</th>
          </tr>
        </thead>
        <tbody>
          <TotalsRow teamId={awayTeamId} totals={totals.away} accent={awayAccent} />
          <TotalsRow teamId={homeTeamId} totals={totals.home} accent={homeAccent} />
        </tbody>
      </table>

      {stars.length > 0 && (
        <div className="mt-3 border-t border-line pt-2.5">
          <div className="mb-1.5 text-xs font-medium text-muted">Standouts</div>
          <div className="flex flex-wrap gap-1.5">
            {stars.map((star) => (
              <span
                key={star.name}
                className="rounded-md border border-line bg-raised px-2 py-1 text-xs text-ink"
              >
                <span className="font-medium">{star.name}</span>
                <span className="text-faint"> · {star.line}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TotalsRow({
  teamId,
  totals,
  accent,
}: {
  teamId: number;
  totals: TeamTotals;
  accent: string;
}) {
  return (
    <tr>
      <td className="py-1 text-left">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-1 rounded-sm"
            style={{ background: accent }}
            aria-hidden
          />
          <span className="text-muted">{teamLabel(teamId).abbr}</span>
        </span>
      </td>
      <td className="px-2 py-1 text-right font-medium text-ink">{totals.runs}</td>
      <td className="px-2 py-1 text-right text-ink">{totals.hits}</td>
      <td className="px-2 py-1 text-right text-ink">{totals.homeRuns}</td>
      <td className="px-2 py-1 text-right text-ink">{totals.walks}</td>
    </tr>
  );
}

function emptyTotals(): TeamTotals {
  return { runs: 0, hits: 0, homeRuns: 0, walks: 0 };
}

function summarize(plays: Play[], homeTeamId: number) {
  const totals = { home: emptyTotals(), away: emptyTotals() };
  const batters = new Map<string, { hits: number; homeRuns: number; rbi: number }>();

  for (const play of plays) {
    if (play.event === "tiebreaker") continue;
    const side = play.batting_team_id === homeTeamId ? totals.home : totals.away;
    side.runs += play.runs_scored_on_play;
    if (HIT_EVENTS.has(play.event)) side.hits += 1;
    if (play.event === "home_run") side.homeRuns += 1;
    if (play.event === "walk") side.walks += 1;

    const name = play.batter_name;
    if (!name) continue;
    const entry = batters.get(name) ?? { hits: 0, homeRuns: 0, rbi: 0 };
    if (HIT_EVENTS.has(play.event)) entry.hits += 1;
    if (play.event === "home_run") entry.homeRuns += 1;
    entry.rbi += play.runs_scored_on_play;
    batters.set(name, entry);
  }

  const stars = [...batters.entries()]
    .map(([name, stat]) => ({
      name,
      score: stat.homeRuns * 3 + stat.hits + stat.rbi,
      line: [
        stat.hits > 0 ? `${stat.hits} H` : null,
        stat.homeRuns > 0 ? `${stat.homeRuns} HR` : null,
        stat.rbi > 0 ? `${stat.rbi} RBI` : null,
      ]
        .filter(Boolean)
        .join(" · "),
    }))
    .filter((star) => star.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 4);

  return { totals, stars };
}
