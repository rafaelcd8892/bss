import { Link, useOutletContext, useSearchParams } from "react-router-dom";
import type { MetricComparison } from "../../api/client";
import type { components } from "../../api/schema";
import type { ShellContext } from "../../components/AppShell";
import { Card } from "../../components/Card";
import { pairAccents } from "../../teams";
import {
  COMPARE_METRIC_ORDER,
  METRIC_HINTS,
  METRIC_LABELS,
  type CompareMetric,
  formatMetric,
  goodnessRatio,
} from "./metrics";
import { PlayerHeadshot } from "../../components/PlayerHeadshot";
import { TeamLogo } from "../../components/TeamLogo";
import { usePlayerSeason } from "../catalog/hooks";
import { PlayerSearch } from "./PlayerSearch";
import { SeasonLineRow } from "./SeasonLineRow";
import { usePlayerCompare } from "./usePlayerCompare";

const DEFAULT_SEED = 1234;
type Side = "left" | "right";
type SearchResult = components["schemas"]["PlayerSearchResult"];

export function CompareView() {
  const { dark } = useOutletContext<ShellContext>();
  const [params, setParams] = useSearchParams();

  const leftPlayerId = positiveInt(params.get("left"));
  const rightPlayerId = positiveInt(params.get("right"));
  const seed = positiveInt(params.get("seed")) ?? DEFAULT_SEED;
  const season = positiveInt(params.get("season"));

  const leftSeasonTeam = positiveInt(params.get("leftTeam"));
  const rightSeasonTeam = positiveInt(params.get("rightTeam"));
  const { data, loading, error } = usePlayerCompare(leftPlayerId, rightPlayerId, seed, season);
  // The season endpoint carries the identity and the full stat line, so the header no
  // longer depends on the player happening to be in the loaded club roster — a
  // deep-linked player used to render as a bare id.
  const leftSeason = usePlayerSeason(leftPlayerId, season);
  const rightSeason = usePlayerSeason(rightPlayerId, season);

  /** The club travels in the URL beside the player, so a shared link keeps its colors
   *  before the season request has come back. */
  function selectPlayer(side: Side, result: SearchResult | null) {
    const teamKey = side === "left" ? "leftTeam" : "rightTeam";
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (result === null) {
          next.delete(side);
          next.delete(teamKey);
        } else {
          next.set(side, String(result.player_id));
          if (result.team_id) next.set(teamKey, String(result.team_id));
          else next.delete(teamKey);
        }
        return next;
      },
      { replace: true },
    );
  }

  const leftName = leftSeason.data?.player?.full_name ?? `#${leftPlayerId ?? ""}`;
  const rightName = rightSeason.data?.player?.full_name ?? `#${rightPlayerId ?? ""}`;
  // The club follows the player once his season is known; the URL carries it in the
  // meantime so a shared link is not colourless while the request is in flight.
  const leftTeamId = leftSeason.data?.lines?.[0]?.team_id ?? leftSeasonTeam;
  const rightTeamId = rightSeason.data?.lines?.[0]?.team_id ?? rightSeasonTeam;
  // Two clubs shown together must stay visually distinct, same as a matchup.
  const accents = pairAccents(leftTeamId ?? 0, rightTeamId ?? 0, dark);
  // Whichever side has a career offers the years; a deep link can name any of them.
  const seasonOptions =
    leftSeason.data?.available_seasons?.length
      ? leftSeason.data.available_seasons
      : (rightSeason.data?.available_seasons ?? []);

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2.5 max-[560px]:grid-cols-1">
        <PlayerSearch
          label="left"
          dark={dark}
          accent={leftPlayerId !== null ? accents.first : undefined}
          selected={
            leftPlayerId !== null
              ? { playerId: leftPlayerId, name: leftName, teamId: leftTeamId }
              : null
          }
          onSelect={(result) => selectPlayer("left", result)}
        />
        <PlayerSearch
          label="right"
          dark={dark}
          accent={rightPlayerId !== null ? accents.second : undefined}
          selected={
            rightPlayerId !== null
              ? { playerId: rightPlayerId, name: rightName, teamId: rightTeamId }
              : null
          }
          onSelect={(result) => selectPlayer("right", result)}
        />
      </div>

      {seasonOptions.length > 1 && (
        <div className="flex items-center gap-2 px-1">
          <label className="flex items-center gap-1.5 text-xs text-faint">
            season
            <select
              value={data?.season ?? season ?? ""}
              onChange={(event) =>
                setParams(
                  (previous) => {
                    const next = new URLSearchParams(previous);
                    next.set("season", event.target.value);
                    return next;
                  },
                  { replace: true },
                )
              }
              className="rounded-md border border-line bg-surface px-1.5 py-1 text-xs text-ink outline-none"
            >
              {seasonOptions.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </label>
          <span className="text-[11px] text-faint">
            compares both players as they were that year
          </span>
        </div>
      )}

      {error && (
        <Card className="px-4 py-5">
          <p className="text-[13px] text-ink">{error}</p>
        </Card>
      )}

      {!error && (leftPlayerId === null || rightPlayerId === null) && (
        <Card className="px-4 py-6">
          <p className="text-[13px] text-muted">
            Search for a player on each side to compare them across wOBA, xwOBA, wRC+,
            FIP and K/BB.
          </p>
        </Card>
      )}

      {!error && data && leftPlayerId !== null && rightPlayerId !== null && (
        <ComparisonTable
          data={data}
          leftName={leftName}
          rightName={rightName}
          leftAccent={accents.first}
          rightAccent={accents.second}
          leftTeamId={leftTeamId}
          rightTeamId={rightTeamId}
          leftLines={leftSeason.data?.lines ?? []}
          rightLines={rightSeason.data?.lines ?? []}
          dark={dark}
          loading={loading}
        />
      )}
    </div>
  );
}

type Line = components["schemas"]["PlayerSeasonLine"];

type ComparisonTableProps = {
  data: {
    metrics: { [key: string]: MetricComparison };
    left_player_id: number;
    right_player_id: number;
    season?: number | null;
  };
  leftName: string;
  rightName: string;
  leftAccent: string;
  rightAccent: string;
  leftTeamId: number | null;
  rightTeamId: number | null;
  leftLines: Line[];
  rightLines: Line[];
  dark: boolean;
  loading: boolean;
};

function ComparisonTable({
  data,
  leftName,
  rightName,
  leftAccent,
  rightAccent,
  leftTeamId,
  rightTeamId,
  leftLines,
  rightLines,
  dark,
  loading,
}: ComparisonTableProps) {
  const rows = COMPARE_METRIC_ORDER.map((metric) => ({
    metric,
    comparison: data.metrics[metric],
  })).filter((row): row is { metric: CompareMetric; comparison: MetricComparison } =>
    Boolean(row.comparison),
  );

  // A verdict only means something when both sides were actually measured.
  const measured = rows.filter(
    (row) => row.comparison.left_source === "real" && row.comparison.right_source === "real",
  );
  const leftWins = measured.filter(
    (row) => row.comparison.better_player_id === data.left_player_id,
  ).length;
  const seededCount = rows.length - measured.length;

  return (
    <Card padded={false} className={loading ? "opacity-60" : ""}>
      <div className="grid grid-cols-[minmax(0,1fr)_78px_minmax(0,1fr)] items-center gap-2 border-b border-line px-3.5 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="h-3.5 w-1 shrink-0 rounded-sm" style={{ background: leftAccent }} />
          <PlayerHeadshot
            playerId={data.left_player_id}
            name={leftName}
            size={30}
            accent={leftAccent}
          />
          <Link
            to={`/explore/players/${data.left_player_id}`}
            className="truncate text-sm font-medium text-ink underline-offset-2 hover:underline"
          >
            {leftName}
          </Link>
          {leftTeamId !== null && <TeamLogo teamId={leftTeamId} dark={dark} size={16} />}
        </div>
        <span className="text-center text-[11px] text-faint">vs</span>
        <div className="flex min-w-0 items-center justify-end gap-2">
          {rightTeamId !== null && <TeamLogo teamId={rightTeamId} dark={dark} size={16} />}
          <Link
            to={`/explore/players/${data.right_player_id}`}
            className="truncate text-right text-sm font-medium text-ink underline-offset-2 hover:underline"
          >
            {rightName}
          </Link>
          <PlayerHeadshot
            playerId={data.right_player_id}
            name={rightName}
            size={30}
            accent={rightAccent}
          />
          <span className="h-3.5 w-1 shrink-0 rounded-sm" style={{ background: rightAccent }} />
        </div>
      </div>

      <div className="flex flex-col">
        {rows.map(({ metric, comparison }) => (
          <MetricRow
            key={metric}
            metric={metric}
            comparison={comparison}
            leftPlayerId={data.left_player_id}
            leftAccent={leftAccent}
            rightAccent={rightAccent}
          />
        ))}
      </div>

      {(["hitting", "pitching"] as const).map((group) => (
        <SeasonLineRow
          key={group}
          group={group}
          left={leftLines.find((line) => line.stat_group === group) ?? null}
          right={rightLines.find((line) => line.stat_group === group) ?? null}
        />
      ))}

      <div className="border-t border-line px-3.5 py-2.5 text-xs text-muted">
        {measured.length > 0 ? (
          <>
            {leftName} leads <span className="text-ink">{leftWins}</span> of{" "}
            <span className="text-ink">{measured.length}</span> measured metric
            {measured.length === 1 ? "" : "s"}.
          </>
        ) : (
          <>No metric is measured for both players, so there is nothing to conclude.</>
        )}
        {seededCount > 0 && (
          <span className="text-faint">
            {" "}
            {seededCount} seeded metric{seededCount === 1 ? " is" : "s are"} shown for shape
            only and excluded from the verdict.
          </span>
        )}
      </div>
    </Card>
  );
}

type MetricRowProps = {
  metric: CompareMetric;
  comparison: MetricComparison;
  leftPlayerId: number;
  leftAccent: string;
  rightAccent: string;
};

function MetricRow({
  metric,
  comparison,
  leftPlayerId,
  leftAccent,
  rightAccent,
}: MetricRowProps) {
  const bothReal =
    comparison.left_source === "real" && comparison.right_source === "real";
  const leftWins = bothReal && comparison.better_player_id === leftPlayerId;
  const rightWins = bothReal && comparison.better_player_id !== leftPlayerId;

  const leftRatio = goodnessRatio(
    comparison.direction,
    comparison.left_value,
    comparison.right_value,
  );
  const rightRatio = goodnessRatio(
    comparison.direction,
    comparison.right_value,
    comparison.left_value,
  );

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_78px_minmax(0,1fr)] items-center gap-2 border-b border-line px-3.5 py-2 last:border-b-0">
      <SideValue
        metric={metric}
        value={comparison.left_value}
        source={comparison.left_source}
        ratio={leftRatio}
        accent={leftAccent}
        winner={leftWins}
        align="right"
      />
      <div className="text-center" title={METRIC_HINTS[metric]}>
        <div className="text-xs font-medium text-muted">{METRIC_LABELS[metric]}</div>
        {!bothReal && <div className="text-[10px] text-faint">seeded</div>}
      </div>
      <SideValue
        metric={metric}
        value={comparison.right_value}
        source={comparison.right_source}
        ratio={rightRatio}
        accent={rightAccent}
        winner={rightWins}
        align="left"
      />
    </div>
  );
}

type SideValueProps = {
  metric: CompareMetric;
  value: number;
  source: "real" | "synthetic";
  ratio: number;
  accent: string;
  winner: boolean;
  align: "left" | "right";
};

function SideValue({
  metric,
  value,
  source,
  ratio,
  accent,
  winner,
  align,
}: SideValueProps) {
  const seeded = source === "synthetic";
  const number = (
    <span
      className={`shrink-0 font-mono text-sm tabular-nums ${
        seeded ? "text-faint italic" : winner ? "font-medium text-ink" : "text-muted"
      }`}
    >
      {formatMetric(metric, value)}
    </span>
  );
  const bar = (
    <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-raised">
      <span
        className="block h-full rounded-full"
        style={{
          width: `${Math.round(ratio * 100)}%`,
          background: seeded ? "var(--color-line-strong)" : accent,
          opacity: seeded ? 0.5 : winner ? 1 : 0.55,
          marginLeft: align === "right" ? "auto" : undefined,
        }}
      />
    </span>
  );

  return (
    <div
      className={`flex min-w-0 items-center gap-2 ${
        align === "right" ? "flex-row" : "flex-row-reverse"
      }`}
    >
      {bar}
      {number}
    </div>
  );
}

function positiveInt(raw: string | null): number | null {
  if (raw === null) return null;
  const value = Number(raw);
  return Number.isFinite(value) && value > 0 ? Math.floor(value) : null;
}
