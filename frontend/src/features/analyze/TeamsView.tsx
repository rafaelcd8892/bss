import { useMemo } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import type { TeamProfile } from "../../api/client";
import type { ShellContext } from "../../components/AppShell";
import { Card } from "../../components/Card";
import { teamAccent, teamLabel } from "../../teams";
import { useTeamProfiles } from "./useTeamProfiles";

/** Columns the league table can sort on, in the simulator's own factor order. */
const FACTOR_COLUMNS = [
  { key: "offense", label: "off", hint: "Offense, from team wOBA" },
  { key: "discipline", label: "disc", hint: "Walk rate" },
  { key: "power", label: "pow", hint: "Isolated power" },
  { key: "speed", label: "spd", hint: "Stolen-base rate" },
  {
    key: "prevention",
    label: "prev",
    hint: "Run prevention, from team FIP (inverted)",
  },
  { key: "command", label: "cmd", hint: "Team strikeout-to-walk ratio" },
  {
    key: "range_factor",
    label: "rng",
    hint: "Fielding range: plays made against what the league makes at the same positions",
  },
] as const;

type FactorKey = (typeof FACTOR_COLUMNS)[number]["key"];
type SortKey = "team" | "woba" | "fip" | FactorKey;

/** Columns where a lower number is the better one, so "best first" means ascending. */
const LOWER_IS_BETTER: ReadonlySet<SortKey> = new Set<SortKey>(["fip"]);

function bestFirstDirection(key: SortKey): "asc" | "desc" {
  if (key === "team") return "asc";
  return LOWER_IS_BETTER.has(key) ? "asc" : "desc";
}

export function TeamsView() {
  const { dark } = useOutletContext<ShellContext>();
  const [params, setParams] = useSearchParams();
  const { teams, season, loading, error } = useTeamProfiles();

  const sort = (params.get("sort") ?? "offense") as SortKey;
  const descending = (params.get("dir") ?? "desc") === "desc";

  const rows = useMemo(() => sortTeams(teams, sort, descending), [teams, sort, descending]);
  const synthetic = teams.filter((team) => team.source === "synthetic").length;

  function toggleSort(key: SortKey) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        const sameColumn = (previous.get("sort") ?? "offense") === key;
        const currentDirection = previous.get("dir") ?? "desc";
        next.set("sort", key);
        // A new column opens on "best first" — which is ascending for FIP, where a
        // lower number is the better one. Clicking the same column again flips it.
        next.set(
          "dir",
          sameColumn ? (currentDirection === "desc" ? "asc" : "desc") : bestFirstDirection(key),
        );
        return next;
      },
      { replace: true },
    );
  }

  if (error) {
    return (
      <Card className="px-4 py-5">
        <p className="text-[13px] text-ink">{error}</p>
        <p className="mt-1.5 text-xs text-muted">
          Run the ingestion, then set <span className="font-mono">BASEBALL_STATS_SOURCE</span> to{" "}
          <span className="font-mono">postgres</span> and restart the API.
        </p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <Card padded={false}>
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-3.5 py-2.5">
          <span className="text-sm font-medium text-ink">Team profiles</span>
          <span className="text-xs text-faint">
            {loading
              ? "loading…"
              : `${teams.length} clubs · the seven factors the simulator consumes · season ${season}`}
          </span>
        </div>

        {loading && teams.length === 0 ? (
          <p className="px-3.5 py-5 text-sm text-faint">Loading team profiles…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="text-xs text-faint">
                  <SortHeader
                    label="team"
                    column="team"
                    sort={sort}
                    descending={descending}
                    onSort={toggleSort}
                    align="left"
                  />
                  <SortHeader
                    label="wOBA"
                    column="woba"
                    sort={sort}
                    descending={descending}
                    onSort={toggleSort}
                    hint="Aggregate team wOBA behind the offense factor"
                  />
                  <SortHeader
                    label="FIP"
                    column="fip"
                    sort={sort}
                    descending={descending}
                    onSort={toggleSort}
                    hint="Aggregate team FIP behind the prevention factor"
                  />
                  {FACTOR_COLUMNS.map((column) => (
                    <SortHeader
                      key={column.key}
                      label={column.label}
                      column={column.key}
                      sort={sort}
                      descending={descending}
                      onSort={toggleSort}
                      hint={column.hint}
                    />
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((team) => (
                  <TeamRow key={team.team_id} team={team} dark={dark} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <p className="px-1 text-[11px] leading-relaxed text-faint">
        Factors are league-relative on a 0–1 scale, so 0.5 is roughly average. Range compares each
        club's plays made per nine innings against the league at the same positions, so it reflects
        defense rather than which positions a club happens to field; a dash means no fielding was
        ingested for that club.
        {synthetic > 0 &&
          ` ${synthetic} club(s) have no ingested stats and fall back to seeded values.`}
      </p>
    </div>
  );
}

type SortHeaderProps = {
  label: string;
  column: SortKey;
  sort: SortKey;
  descending: boolean;
  onSort: (key: SortKey) => void;
  align?: "left" | "right";
  hint?: string;
};

function SortHeader({
  label,
  column,
  sort,
  descending,
  onSort,
  align = "right",
  hint,
}: SortHeaderProps) {
  const active = sort === column;
  return (
    <th
      scope="col"
      className={`font-normal ${align === "left" ? "px-3.5 text-left" : "px-2 text-right"}`}
      aria-sort={active ? (descending ? "descending" : "ascending") : "none"}
    >
      <button
        onClick={() => onSort(column)}
        title={hint}
        className={`py-2 transition-colors hover:text-ink ${active ? "text-ink" : ""}`}
      >
        {label}
        {active && <span aria-hidden> {descending ? "↓" : "↑"}</span>}
      </button>
    </th>
  );
}

function TeamRow({ team, dark }: { team: TeamProfile; dark: boolean }) {
  const label = teamLabel(team.team_id);
  const accent = teamAccent(team.team_id, dark);
  const counted =
    `${team.batters_counted} batting, ${team.pitchers_counted} pitching` +
    ` and ${team.fielders_counted} fielding lines`;

  return (
    <tr className="border-t border-line" title={`${label.name} — built from ${counted}`}>
      <td className="px-3.5 py-1.5">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-1 shrink-0 rounded-sm"
            style={{ background: accent }}
            aria-hidden
          />
          <span className="text-xs text-ink">{label.abbr}</span>
          {team.source === "synthetic" && (
            <span className="rounded bg-raised px-1 text-[10px] text-faint">seeded</span>
          )}
        </span>
      </td>
      <td className="px-2 py-1.5 text-right font-mono text-xs text-muted">
        {team.team_woba !== null && team.team_woba !== undefined
          ? team.team_woba.toFixed(3).replace(/^0\./, ".")
          : "—"}
      </td>
      <td className="px-2 py-1.5 text-right font-mono text-xs text-muted">
        {team.team_fip !== null && team.team_fip !== undefined ? team.team_fip.toFixed(2) : "—"}
      </td>
      {FACTOR_COLUMNS.map((column) => (
        <FactorCell
          key={column.key}
          value={team.factors[column.key]}
          accent={accent}
          // Range without fielding lines is the neutral placeholder, not a
          // measurement, so the cell stays empty rather than reading 0.50.
          measured={column.key !== "range_factor" || team.fielders_counted > 0}
        />
      ))}
    </tr>
  );
}

/** The number plus a bar behind it, so a column can be scanned at a glance. */
function FactorCell({
  value,
  accent,
  measured = true,
}: {
  value: number;
  accent: string;
  measured?: boolean;
}) {
  if (!measured) {
    return <td className="px-2 py-1.5 text-right font-mono text-xs text-faint">—</td>;
  }
  return (
    <td className="px-2 py-1.5">
      <div className="relative flex h-5 items-center justify-end">
        <span
          className="absolute inset-y-0 right-0 rounded-sm"
          style={{
            width: `${Math.round(Math.min(Math.max(value, 0), 1) * 100)}%`,
            background: accent,
            opacity: 0.18,
          }}
          aria-hidden
        />
        <span className="relative font-mono text-xs text-ink">{value.toFixed(2)}</span>
      </div>
    </td>
  );
}

function sortTeams(teams: TeamProfile[], sort: SortKey, descending: boolean): TeamProfile[] {
  const direction = descending ? -1 : 1;
  return [...teams].sort((a, b) => {
    if (sort === "team") {
      return direction * teamLabel(a.team_id).abbr.localeCompare(teamLabel(b.team_id).abbr);
    }
    const left = sortValue(a, sort);
    const right = sortValue(b, sort);
    // Clubs with no ingested value sort last in BOTH directions, so applying the
    // direction inside the comparator rather than reversing the finished list.
    if (left === null && right === null) return 0;
    if (left === null) return 1;
    if (right === null) return -1;
    return direction * (left - right);
  });
}

function sortValue(team: TeamProfile, sort: SortKey): number | null {
  if (sort === "woba") return team.team_woba ?? null;
  if (sort === "fip") return team.team_fip ?? null;
  if (sort === "team") return null;
  return team.factors[sort];
}
