import { useOutletContext, useSearchParams } from "react-router-dom";
import type { MetricComparison } from "../../api/client";
import type { ShellContext } from "../../components/AppShell";
import { Card } from "../../components/Card";
import { pairAccents } from "../../teams";
import { useTeamCatalog } from "../../useTeamCatalog";
import {
  COMPARE_METRIC_ORDER,
  METRIC_HINTS,
  METRIC_LABELS,
  type CompareMetric,
  formatMetric,
  goodnessRatio,
} from "./metrics";
import { useRoster, type RosterPlayer } from "./useRoster";
import { usePlayerCompare } from "./usePlayerCompare";

const DEFAULT_SEED = 1234;
const SELECT =
  "w-full min-w-0 rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink outline-none";

type Side = "left" | "right";

export function CompareView() {
  const { dark } = useOutletContext<ShellContext>();
  const [params, setParams] = useSearchParams();
  const teams = useTeamCatalog();

  const leftTeamId = positiveInt(params.get("leftTeam")) ?? teams[0]?.id ?? null;
  const rightTeamId = positiveInt(params.get("rightTeam")) ?? teams[1]?.id ?? null;
  const leftPlayerId = positiveInt(params.get("left"));
  const rightPlayerId = positiveInt(params.get("right"));
  const seed = positiveInt(params.get("seed")) ?? DEFAULT_SEED;

  // Two clubs shown together must stay visually distinct, same as a matchup.
  const accents = pairAccents(leftTeamId ?? 0, rightTeamId ?? 0, dark);

  const leftRoster = useRoster(leftTeamId);
  const rightRoster = useRoster(rightTeamId);
  const { data, loading, error } = usePlayerCompare(leftPlayerId, rightPlayerId, seed);

  function updateSide(side: Side, patch: { team?: number; player?: number | null }) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (patch.team !== undefined) {
          next.set(side === "left" ? "leftTeam" : "rightTeam", String(patch.team));
          // The previous pick belongs to the old roster, so it cannot carry over.
          next.delete(side);
        }
        if (patch.player !== undefined) {
          if (patch.player === null) next.delete(side);
          else next.set(side, String(patch.player));
        }
        return next;
      },
      { replace: true },
    );
  }

  const leftName = playerName(leftRoster.players, leftPlayerId);
  const rightName = playerName(rightRoster.players, rightPlayerId);

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2.5 max-[560px]:grid-cols-1">
        <PlayerPicker
          label="left"
          accent={leftTeamId !== null ? accents.first : undefined}
          teams={teams}
          teamId={leftTeamId}
          playerId={leftPlayerId}
          roster={leftRoster}
          onTeam={(team) => updateSide("left", { team })}
          onPlayer={(player) => updateSide("left", { player })}
        />
        <PlayerPicker
          label="right"
          accent={rightTeamId !== null ? accents.second : undefined}
          teams={teams}
          teamId={rightTeamId}
          playerId={rightPlayerId}
          roster={rightRoster}
          onTeam={(team) => updateSide("right", { team })}
          onPlayer={(player) => updateSide("right", { player })}
        />
      </div>

      {error && (
        <Card className="px-4 py-5">
          <p className="text-[13px] text-ink">{error}</p>
        </Card>
      )}

      {!error && (leftPlayerId === null || rightPlayerId === null) && (
        <Card className="px-4 py-6">
          <p className="text-[13px] text-muted">
            Pick a player on each side to compare them across wOBA, xwOBA, wRC+, FIP and K/BB.
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
          loading={loading}
        />
      )}
    </div>
  );
}

type PickerProps = {
  label: string;
  accent?: string;
  teams: ReturnType<typeof useTeamCatalog>;
  teamId: number | null;
  playerId: number | null;
  roster: { players: RosterPlayer[]; loading: boolean };
  onTeam: (teamId: number) => void;
  onPlayer: (playerId: number | null) => void;
};

function PlayerPicker({
  label,
  accent,
  teams,
  teamId,
  playerId,
  roster,
  onTeam,
  onPlayer,
}: PickerProps) {
  const known = roster.players.some((player) => player.player_id === playerId);

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-line bg-surface px-3 py-2.5"
      style={accent ? { borderLeft: `4px solid ${accent}` } : undefined}
    >
      <span className="text-xs text-muted">{label}</span>
      <select
        aria-label={`${label} team`}
        value={teamId ?? ""}
        onChange={(event) => onTeam(Number(event.target.value))}
        className={SELECT}
      >
        {teams.map((team) => (
          <option key={team.id} value={team.id}>
            {team.name}
          </option>
        ))}
      </select>
      <select
        aria-label={`${label} player`}
        value={known && playerId !== null ? playerId : ""}
        onChange={(event) =>
          onPlayer(event.target.value === "" ? null : Number(event.target.value))
        }
        className={SELECT}
        disabled={roster.loading || roster.players.length === 0}
      >
        <option value="">
          {roster.loading
            ? "loading roster…"
            : roster.players.length === 0
              ? "no roster ingested"
              : "select a player"}
        </option>
        {roster.players.map((player) => (
          <option key={player.player_id} value={player.player_id}>
            {player.full_name}
            {player.primary_position ? ` · ${player.primary_position}` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}

type ComparisonTableProps = {
  data: { metrics: { [key: string]: MetricComparison }; left_player_id: number };
  leftName: string;
  rightName: string;
  leftAccent: string;
  rightAccent: string;
  loading: boolean;
};

function ComparisonTable({
  data,
  leftName,
  rightName,
  leftAccent,
  rightAccent,
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
        <div className="flex items-center gap-2">
          <span className="h-3.5 w-1 shrink-0 rounded-sm" style={{ background: leftAccent }} />
          <span className="truncate text-sm font-medium text-ink">{leftName}</span>
        </div>
        <span className="text-center text-[11px] text-faint">vs</span>
        <div className="flex items-center justify-end gap-2">
          <span className="truncate text-right text-sm font-medium text-ink">{rightName}</span>
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

function playerName(players: RosterPlayer[], playerId: number | null): string {
  if (playerId === null) return "—";
  return players.find((player) => player.player_id === playerId)?.full_name ?? `#${playerId}`;
}

function positiveInt(raw: string | null): number | null {
  if (raw === null) return null;
  const value = Number(raw);
  return Number.isFinite(value) && value > 0 ? Math.floor(value) : null;
}
