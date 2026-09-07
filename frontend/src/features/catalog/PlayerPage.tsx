import { Link, useOutletContext, useParams, useSearchParams } from "react-router-dom";
import type { components } from "../../api/schema";
import type { ShellContext } from "../../components/AppShell";
import { Card } from "../../components/Card";
import { PlayerHeadshot } from "../../components/PlayerHeadshot";
import { teamAccent, teamLabel } from "../../teams";
import { formatMetric } from "../analyze/metrics";
import { usePlayerSeason } from "./hooks";

type Line = components["schemas"]["PlayerSeasonLine"];

/**
 * The seasons this player actually has, rather than a free year input.
 *
 * The list comes from the API, so it can only offer years with an ingested line —
 * picking one that turns out to be empty is not a state worth building.
 */
function SeasonPicker({
  season,
  available,
  onChange,
}: {
  season: number;
  available: number[] | undefined;
  onChange: (season: number) => void;
}) {
  // Tolerates an API that predates the field rather than blanking the page.
  if (!available || available.length <= 1) {
    return <span className="ml-auto shrink-0 text-xs text-faint">season {season}</span>;
  }
  return (
    <label className="ml-auto flex shrink-0 items-center gap-1.5 text-xs text-faint">
      season
      <select
        value={season}
        onChange={(event) => onChange(Number(event.target.value))}
        className="rounded-md border border-line bg-surface px-1.5 py-1 text-xs text-ink outline-none"
      >
        {available.map((year) => (
          <option key={year} value={year}>
            {year}
          </option>
        ))}
      </select>
    </label>
  );
}

export function PlayerPage() {
  const { dark } = useOutletContext<ShellContext>();
  const { playerId } = useParams();
  const id = Number(playerId);
  const valid = Number.isFinite(id) && id > 0;
  // The season lives in the URL, so a particular year of a career is linkable.
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get("season"));
  const season = Number.isFinite(requested) && requested > 0 ? requested : null;
  const { data, loading, error } = usePlayerSeason(valid ? id : null, season);

  if (!valid || error) {
    return (
      <Card className="px-4 py-5">
        <p className="text-[13px] text-ink">
          {valid ? "That player was not found." : "That is not a valid player."}
        </p>
        <Link to="/explore" className="mt-2 inline-block text-xs text-muted hover:text-ink">
          Back to clubs
        </Link>
      </Card>
    );
  }

  if (loading || !data) {
    return <Card className="px-4 py-5">
      <p className="text-sm text-faint">Loading player…</p>
    </Card>;
  }

  const teamId = data.lines.find((line) => line.team_id)?.team_id ?? null;
  const accent = teamId !== null ? teamAccent(teamId, dark) : "var(--color-line-strong)";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 text-xs text-muted">
        <Link to="/explore" className="hover:text-ink">
          Clubs
        </Link>
        {teamId !== null && (
          <>
            <span aria-hidden>/</span>
            <Link to={`/explore/teams/${teamId}`} className="hover:text-ink">
              {teamLabel(teamId).abbr}
            </Link>
          </>
        )}
        <span aria-hidden>/</span>
        <span className="text-ink">{data.player.full_name}</span>
      </div>

      <Card>
        <div className="flex items-center gap-3">
          <span className="h-8 w-1.5 shrink-0 rounded-sm" style={{ background: accent }} aria-hidden />
          <PlayerHeadshot
            playerId={data.player.player_id}
            name={data.player.full_name}
            size={44}
            accent={accent}
          />
          <div className="min-w-0">
            <h2 className="truncate text-base font-medium text-ink">{data.player.full_name}</h2>
            <p className="text-xs text-muted">
              {[
                data.player.primary_position,
                teamId !== null ? teamLabel(teamId).name : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <SeasonPicker
            season={data.season}
            available={data.available_seasons}
            onChange={(next) =>
              setParams((previous) => {
                const query = new URLSearchParams(previous);
                query.set("season", String(next));
                return query;
              })
            }
          />
        </div>
      </Card>

      {data.lines.length === 0 ? (
        <Card className="px-4 py-5">
          <p className="text-[13px] text-muted">
            No season stats ingested for this player. Run the ingestion with{" "}
            <span className="font-mono">--include-player-stats</span> to populate them.
          </p>
        </Card>
      ) : (
        data.lines.map((line) => <SeasonLine key={line.stat_group} line={line} />)
      )}
    </div>
  );
}

function SeasonLine({ line }: { line: Line }) {
  const hitting = line.stat_group === "hitting";
  const counting = hitting
    ? [
        ["PA", line.plate_appearances],
        ["AB", line.at_bats],
        ["H", line.hits],
        ["2B", line.doubles],
        ["3B", line.triples],
        ["HR", line.home_runs],
        ["BB", line.walks],
        ["SO", line.strikeouts],
        ["SB", line.stolen_bases],
      ]
    : [
        ["IP", line.innings_pitched],
        ["SO", line.strikeouts],
        ["BB", line.walks],
        ["HR", line.home_runs],
      ];

  const rates = hitting
    ? [
        ["wOBA", line.woba, "woba"] as const,
        ["wRC+", line.wrc_plus, "wrc_plus"] as const,
      ]
    : [
        ["FIP", line.fip, "fip"] as const,
        ["K/BB", line.k_bb_ratio, "k_bb_ratio"] as const,
      ];

  return (
    <Card padded={false}>
      <div className="border-b border-line px-3.5 py-2 text-sm font-medium text-ink">
        {hitting ? "Hitting" : "Pitching"}
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-2 px-3.5 py-2.5">
        {rates.map(([label, value, metric]) => (
          <div key={label}>
            <div className="text-[11px] text-faint">{label}</div>
            <div className="font-mono text-lg text-ink">
              {value !== null && value !== undefined ? formatMetric(metric, value) : "—"}
            </div>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-line px-3.5 py-2">
        {counting.map(([label, value]) => (
          <div key={label as string} className="flex items-baseline gap-1.5">
            <span className="text-[11px] text-faint">{label}</span>
            <span className="font-mono text-xs text-muted">{value ?? "—"}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
