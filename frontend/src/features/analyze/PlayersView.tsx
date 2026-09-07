import { useEffect, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { Link } from "react-router-dom";
import type { components } from "../../api/schema";
import type { ShellContext } from "../../components/AppShell";
import { Card } from "../../components/Card";
import { TeamLogo } from "../../components/TeamLogo";
import { useTeamCatalog } from "../../useTeamCatalog";
import { formatMetric, METRIC_HINTS, type AnyMetric } from "./metrics";
import { useIngestedSeasons } from "./useIngestedSeasons";
import { usePlayerTable, type TableSort } from "./usePlayerTable";

type Row = components["schemas"]["PlayerStatRow"];
type Line = components["schemas"]["PlayerSeasonLine"];

type Column = {
  sort: TableSort;
  label: string;
  metric?: AnyMetric;
  value: (line: Line) => number | null | undefined;
  hint?: string;
};

const HITTING: Column[] = [
  { sort: "pa", label: "PA", value: (l) => l.plate_appearances },
  { sort: "at_bats", label: "AB", value: (l) => l.at_bats },
  { sort: "hits", label: "H", value: (l) => l.hits },
  { sort: "doubles", label: "2B", value: (l) => l.doubles },
  { sort: "triples", label: "3B", value: (l) => l.triples },
  { sort: "home_runs", label: "HR", value: (l) => l.home_runs },
  { sort: "walks", label: "BB", value: (l) => l.walks },
  { sort: "strikeouts", label: "SO", value: (l) => l.strikeouts },
  { sort: "stolen_bases", label: "SB", value: (l) => l.stolen_bases },
  { sort: "batting_average", label: "AVG", metric: "obp", value: (l) => l.batting_average },
  { sort: "obp", label: "OBP", metric: "obp", value: (l) => l.obp },
  { sort: "slg", label: "SLG", metric: "slg", value: (l) => l.slg },
  { sort: "ops", label: "OPS", metric: "ops", value: (l) => l.ops },
  { sort: "iso", label: "ISO", metric: "iso", value: (l) => l.iso },
  { sort: "babip", label: "BABIP", metric: "babip", value: (l) => l.babip },
  { sort: "woba", label: "wOBA", metric: "woba", value: (l) => l.woba },
  { sort: "xwoba", label: "xwOBA", metric: "xwoba", value: (l) => l.xwoba },
  { sort: "wrc_plus", label: "wRC+", metric: "wrc_plus", value: (l) => l.wrc_plus },
];

const PITCHING: Column[] = [
  { sort: "ip", label: "IP", value: (l) => l.innings_pitched },
  { sort: "strikeouts", label: "SO", value: (l) => l.strikeouts },
  { sort: "walks", label: "BB", value: (l) => l.walks },
  { sort: "home_runs", label: "HR", value: (l) => l.home_runs },
  { sort: "era", label: "ERA", metric: "era", value: (l) => l.era },
  { sort: "fip", label: "FIP", metric: "fip", value: (l) => l.fip },
  { sort: "whip", label: "WHIP", metric: "whip", value: (l) => l.whip },
  { sort: "k_bb_ratio", label: "K/BB", metric: "k_bb_ratio", value: (l) => l.k_bb_ratio },
  { sort: "strikeout_rate", label: "K%", metric: "strikeout_rate", value: (l) => l.strikeout_rate },
  { sort: "walk_rate", label: "BB%", metric: "walk_rate", value: (l) => l.walk_rate },
  {
    sort: "ground_ball_rate",
    label: "GB%",
    metric: "ground_ball_rate",
    value: (l) => l.ground_ball_rate,
  },
];

/** Counting stats and most rates read best-first descending; ERA-scale ones ascending. */
const LOWER_IS_BETTER = new Set<TableSort>(["era", "fip", "whip", "walk_rate"]);
const PAGE = 50;

export function PlayersView() {
  const { dark } = useOutletContext<ShellContext>();
  const [params, setParams] = useSearchParams();
  const teams = useTeamCatalog();
  const seasons = useIngestedSeasons();

  const statGroup = params.get("group") === "pitching" ? "pitching" : "hitting";
  const columns = statGroup === "hitting" ? HITTING : PITCHING;
  const defaultSort: TableSort = statGroup === "hitting" ? "pa" : "ip";
  const sortParam = params.get("sort");
  const sort = (columns.some((c) => c.sort === sortParam) ? sortParam : defaultSort) as TableSort;
  const direction = params.get("dir") === "asc" ? "asc" : "desc";
  const teamId = Number(params.get("team")) || null;
  const seasonParam = Number(params.get("season")) || null;
  const minimum = params.get("min") ? Number(params.get("min")) : null;
  const offset = Number(params.get("offset")) || 0;

  // The name filter is typed, so it settles before becoming a request.
  const [searchDraft, setSearchDraft] = useState(params.get("q") ?? "");
  const [search, setSearch] = useState(params.get("q") ?? "");
  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchDraft), 250);
    return () => window.clearTimeout(timer);
  }, [searchDraft]);

  const { data, loading, error } = usePlayerTable({
    statGroup,
    sort,
    direction,
    season: seasonParam,
    teamId,
    search,
    minimum,
    limit: PAGE,
    offset,
  });

  function update(patch: Record<string, string | null>) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        for (const [key, value] of Object.entries(patch)) {
          if (value === null) next.delete(key);
          else next.set(key, value);
        }
        // Any change to what is being asked for restarts the paging: staying on page
        // nine of a different question shows an empty table for no visible reason.
        if (!("offset" in patch)) next.delete("offset");
        return next;
      },
      { replace: true },
    );
  }

  function toggleSort(column: Column) {
    const best = LOWER_IS_BETTER.has(column.sort) ? "asc" : "desc";
    update({
      sort: column.sort,
      // A new column opens best-first; the same column flips.
      dir: sort === column.sort ? (direction === "desc" ? "asc" : "desc") : best,
    });
  }

  const total = data?.total ?? 0;
  const shown = data?.rows.length ?? 0;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-3 rounded-md border border-line bg-surface px-3.5 py-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted">players</span>
          <div className="flex gap-1">
            {(["hitting", "pitching"] as const).map((group) => (
              <button
                key={group}
                onClick={() => update({ group, sort: null, dir: null })}
                aria-pressed={statGroup === group}
                className={`rounded-md border border-line px-2.5 py-1.5 text-xs transition-colors hover:text-ink ${
                  statGroup === group ? "border-ink bg-ink text-app hover:text-app" : "text-muted"
                }`}
              >
                {group === "hitting" ? "batters" : "pitchers"}
              </button>
            ))}
          </div>
        </div>

        <label className="flex flex-col gap-1 text-xs text-muted">
          name
          <input
            type="search"
            value={searchDraft}
            placeholder="filter…"
            onChange={(event) => setSearchDraft(event.target.value)}
            className="w-36 rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink outline-none"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-muted">
          club
          <select
            value={teamId ?? ""}
            onChange={(event) => update({ team: event.target.value || null })}
            className="w-40 rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink outline-none"
          >
            <option value="">whole league</option>
            {teams.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name}
              </option>
            ))}
          </select>
        </label>

        {seasons.length > 1 && (
          <label className="flex flex-col gap-1 text-xs text-muted">
            season
            <select
              value={seasonParam ?? data?.season ?? ""}
              onChange={(event) => update({ season: event.target.value || null })}
              className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink outline-none"
            >
              {seasons.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="flex flex-col gap-1 text-xs text-muted">
          min {statGroup === "hitting" ? "PA" : "IP"}
          <input
            type="number"
            min={0}
            value={params.get("min") ?? ""}
            placeholder="none"
            onChange={(event) => update({ min: event.target.value || null })}
            className="w-20 rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink outline-none"
          />
        </label>
      </div>

      {error ? (
        <Card className="px-4 py-5">
          <p className="text-[13px] text-ink">{error}</p>
        </Card>
      ) : (
        <Card padded={false} className={loading ? "opacity-60" : ""}>
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-3.5 py-2.5">
            <span className="text-sm font-medium text-ink">
              {statGroup === "hitting" ? "Batters" : "Pitchers"}
            </span>
            <span className="text-xs text-faint">
              {loading && !data
                ? "loading…"
                : total === 0
                  ? "no players match"
                  : `${offset + 1}–${offset + shown} of ${total} · season ${data?.season}`}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="text-xs text-faint">
                  <SortHeader
                    label="player"
                    column={{ sort: "name", label: "player", value: () => null }}
                    sort={sort}
                    direction={direction}
                    onSort={toggleSort}
                    align="left"
                  />
                  <th scope="col" className="px-2 py-2 text-left font-normal">
                    team
                  </th>
                  {columns.map((column) => (
                    <SortHeader
                      key={column.sort}
                      label={column.label}
                      column={column}
                      sort={sort}
                      direction={direction}
                      onSort={toggleSort}
                    />
                  ))}
                </tr>
              </thead>
              <tbody>
                {data?.rows.map((row) => (
                  <PlayerRow key={row.player_id} row={row} columns={columns} dark={dark} />
                ))}
              </tbody>
            </table>
          </div>

          {total > PAGE && (
            <div className="flex items-center justify-between gap-2 border-t border-line px-3.5 py-2">
              <button
                onClick={() => update({ offset: String(Math.max(0, offset - PAGE)) })}
                disabled={offset === 0}
                className="rounded-md border border-line px-2 py-1 text-xs text-muted transition-colors hover:text-ink disabled:opacity-40"
              >
                previous
              </button>
              <span className="text-[11px] text-faint">
                page {Math.floor(offset / PAGE) + 1} of {Math.ceil(total / PAGE)}
              </span>
              <button
                onClick={() => update({ offset: String(offset + PAGE) })}
                disabled={offset + shown >= total}
                className="rounded-md border border-line px-2 py-1 text-xs text-muted transition-colors hover:text-ink disabled:opacity-40"
              >
                next
              </button>
            </div>
          )}
        </Card>
      )}

      <p className="px-1 text-[11px] leading-relaxed text-faint">
        Sorting runs over every player who matches, not the page on screen. A metric
        that was never ingested sorts last in both directions — absent is neither best
        nor worst.
      </p>
    </div>
  );
}

function SortHeader({
  label,
  column,
  sort,
  direction,
  onSort,
  align = "right",
}: {
  label: string;
  column: Column;
  sort: TableSort;
  direction: "asc" | "desc";
  onSort: (column: Column) => void;
  align?: "left" | "right";
}) {
  const active = sort === column.sort;
  return (
    <th
      scope="col"
      className={`font-normal ${align === "left" ? "px-3 text-left" : "px-2 text-right"}`}
      aria-sort={active ? (direction === "desc" ? "descending" : "ascending") : "none"}
    >
      <button
        onClick={() => onSort(column)}
        title={column.metric ? METRIC_HINTS[column.metric] : undefined}
        className={`py-2 transition-colors hover:text-ink ${active ? "text-ink" : ""}`}
      >
        {label}
        {active && <span aria-hidden> {direction === "desc" ? "↓" : "↑"}</span>}
      </button>
    </th>
  );
}

function PlayerRow({ row, columns, dark }: { row: Row; columns: Column[]; dark: boolean }) {
  return (
    <tr className="border-t border-line">
      <td className="px-3 py-1.5">
        <Link
          to={`/explore/players/${row.player_id}`}
          className="text-[13px] text-ink underline-offset-2 hover:underline"
        >
          {row.full_name}
        </Link>
      </td>
      <td className="px-2 py-1.5">
        {row.team_id ? (
          <TeamLogo teamId={row.team_id} dark={dark} size={16} />
        ) : (
          <span className="text-[10px] text-faint" title="More than one club">
            multi
          </span>
        )}
      </td>
      {columns.map((column) => {
        const value = column.value(row.line);
        return (
          <td key={column.sort} className="px-2 py-1.5 text-right font-mono text-xs text-muted">
            {value === null || value === undefined
              ? "—"
              : column.metric
                ? formatMetric(column.metric, value)
                : value}
          </td>
        );
      })}
    </tr>
  );
}
