import { Link, useOutletContext, useParams } from "react-router-dom";
import type { ShellContext } from "../../components/AppShell";
import { Card } from "../../components/Card";
import { PlayerHeadshot } from "../../components/PlayerHeadshot";
import { TeamLogo } from "../../components/TeamLogo";
import { teamAccent, teamLabel } from "../../teams";
import { useRoster } from "../../useRoster";
import { useTeamProfile } from "./hooks";

const FACTORS = [
  ["offense", "offense"],
  ["discipline", "discipline"],
  ["power", "power"],
  ["speed", "speed"],
  ["prevention", "prevention"],
  ["command", "command"],
] as const;

export function TeamPage() {
  const { dark } = useOutletContext<ShellContext>();
  const { teamId } = useParams();
  const id = Number(teamId);
  const valid = Number.isFinite(id) && id > 0;

  const label = teamLabel(id);
  const accent = teamAccent(id, dark);
  const profile = useTeamProfile(valid ? id : null);
  const roster = useRoster(valid ? id : null);

  if (!valid) {
    return (
      <Card className="px-4 py-5">
        <p className="text-[13px] text-ink">That is not a valid team.</p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 text-xs text-muted">
        <Link to="/explore" className="hover:text-ink">
          Clubs
        </Link>
        <span aria-hidden>/</span>
        <span className="text-ink">{label.abbr}</span>
      </div>

      <Card>
        <div className="flex items-center gap-3">
          <span className="h-8 w-1.5 shrink-0 rounded-sm" style={{ background: accent }} aria-hidden />
          <TeamLogo teamId={id} dark={dark} size={34} />
          <div className="min-w-0">
            <h2 className="truncate text-base font-medium text-ink">{label.name}</h2>
            <p className="text-xs text-muted">
              {profile.data
                ? profile.data.source === "real"
                  ? `season ${profile.data.season} · built from ${profile.data.batters_counted} batting and ${profile.data.pitchers_counted} pitching lines`
                  : "no ingested stats — the simulator falls back to seeded values"
                : profile.loading
                  ? "loading profile…"
                  : "profile unavailable"}
            </p>
          </div>
        </div>

        {profile.data && profile.data.source === "real" && (
          <div className="mt-3 border-t border-line pt-3">
            <div className="mb-2 flex gap-4 text-xs">
              <span className="text-muted">
                team wOBA{" "}
                <span className="font-mono text-ink">
                  {profile.data.team_woba?.toFixed(3).replace(/^0\./, ".") ?? "—"}
                </span>
              </span>
              <span className="text-muted">
                team FIP{" "}
                <span className="font-mono text-ink">
                  {profile.data.team_fip?.toFixed(2) ?? "—"}
                </span>
              </span>
            </div>
            <dl className="grid grid-cols-3 gap-x-4 gap-y-1.5 max-[480px]:grid-cols-2">
              {FACTORS.map(([key, label]) => (
                <div key={key} className="flex items-center gap-2">
                  <dt className="w-20 shrink-0 text-[11px] text-faint">{label}</dt>
                  <dd className="flex min-w-0 flex-1 items-center gap-1.5">
                    <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-raised">
                      <span
                        className="block h-full rounded-full"
                        style={{
                          width: `${Math.round(profile.data!.factors[key] * 100)}%`,
                          background: accent,
                        }}
                      />
                    </span>
                    <span className="font-mono text-[11px] text-muted">
                      {profile.data!.factors[key].toFixed(2)}
                    </span>
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </Card>

      <Card padded={false}>
        <div className="flex items-baseline justify-between gap-2 border-b border-line px-3.5 py-2.5">
          <span className="text-sm font-medium text-ink">Roster</span>
          <span className="text-xs text-faint">
            {roster.loading ? "loading…" : `${roster.players.length} players`}
          </span>
        </div>
        {!roster.loading && roster.players.length === 0 ? (
          <p className="px-3.5 py-5 text-sm text-faint">
            No roster ingested for this club yet.
          </p>
        ) : (
          <ul>
            {roster.players.map((player) => (
              <li key={player.player_id} className="border-b border-line last:border-b-0">
                <Link
                  to={`/explore/players/${player.player_id}`}
                  className="flex items-center gap-3 px-3.5 py-1.5 transition-colors hover:bg-raised"
                >
                  <PlayerHeadshot
                    playerId={player.player_id}
                    name={player.full_name}
                    size={26}
                    accent={accent}
                  />
                  <span className="w-9 shrink-0 font-mono text-[11px] text-faint">
                    {player.primary_position ?? "—"}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[13px] text-ink">
                    {player.full_name}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
