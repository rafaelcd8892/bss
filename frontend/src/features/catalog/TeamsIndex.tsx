import { Link, useOutletContext } from "react-router-dom";
import type { ShellContext } from "../../components/AppShell";
import { Card } from "../../components/Card";
import { teamAccent } from "../../teams";
import { useTeamCatalog } from "../../useTeamCatalog";

export function TeamsIndex() {
  const { dark } = useOutletContext<ShellContext>();
  const teams = useTeamCatalog();

  return (
    <div className="flex flex-col gap-3">
      <Card padded={false}>
        <div className="flex items-baseline justify-between gap-2 border-b border-line px-3.5 py-2.5">
          <span className="text-sm font-medium text-ink">Clubs</span>
          <span className="text-xs text-faint">{teams.length} teams</span>
        </div>
        <ul className="grid grid-cols-2 max-[560px]:grid-cols-1">
          {teams.map((team) => (
            <li key={team.id} className="border-b border-line">
              <Link
                to={`/explore/teams/${team.id}`}
                className="flex items-center gap-2.5 px-3.5 py-2 transition-colors hover:bg-raised"
              >
                <span
                  className="h-5 w-1 shrink-0 rounded-sm"
                  style={{ background: teamAccent(team.id, dark) }}
                  aria-hidden
                />
                <span className="min-w-0 flex-1 truncate text-[13px] text-ink">{team.name}</span>
                <span className="font-mono text-[11px] text-faint">{team.abbr}</span>
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
