import { useEffect, useState } from "react";
import { api } from "./api/client";
import { allTeams, type TeamLabel } from "./teams";

export type CatalogTeam = TeamLabel & { id: number };

/**
 * Team list for the pickers. Starts from the built-in club list so the UI works with
 * no database, then upgrades to the ingested catalog when the API can serve it.
 */
export function useTeamCatalog(): CatalogTeam[] {
  const [teams, setTeams] = useState<CatalogTeam[]>(() => allTeams());

  useEffect(() => {
    let cancelled = false;
    const builtIn = new Map(allTeams().map((team) => [team.id, team]));

    api
      .GET("/api/v1/teams", {})
      .then(({ data }) => {
        if (cancelled || !data?.teams?.length) return;
        const merged = data.teams.map((team) => {
          const known = builtIn.get(team.team_id);
          return {
            id: team.team_id,
            name: team.name,
            abbr: team.abbreviation ?? known?.abbr ?? `#${team.team_id}`,
            primary: known?.primary ?? "#5f6b7a",
            secondary: known?.secondary ?? "#95a1b0",
          };
        });
        setTeams(merged.sort((a, b) => a.name.localeCompare(b.name)));
      })
      .catch(() => {
        // No database yet: the built-in list is a perfectly good fallback.
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return teams;
}
