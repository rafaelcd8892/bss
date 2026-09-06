import { useEffect, useState } from "react";
import { api, type TeamProfile } from "../../api/client";
import type { components } from "../../api/schema";

export type PlayerSeason = components["schemas"]["PlayerSeasonResponse"];

type Loadable<T> = { data: T | null; loading: boolean; error: string | null };

function useResource<T>(load: () => Promise<T | null>, deps: unknown[]): Loadable<T> {
  const [state, setState] = useState<Loadable<T>>({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState((previous) => ({ ...previous, loading: true, error: null }));

    load()
      .then((data) => {
        if (cancelled) return;
        if (data === null) {
          setState({ data: null, loading: false, error: "Not found." });
          return;
        }
        setState({ data, loading: false, error: null });
      })
      .catch(() => {
        if (!cancelled) {
          setState({
            data: null,
            loading: false,
            error: "Could not load this from the API. Is the stats database available?",
          });
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}

export function useTeamProfile(teamId: number | null): Loadable<TeamProfile> {
  return useResource(async () => {
    if (teamId === null) return null;
    const { data, error } = await api.GET("/api/v1/teams/{team_id}/profile", {
      params: { path: { team_id: teamId } },
    });
    if (error || !data) throw new Error("failed");
    return data;
  }, [teamId]);
}

export function usePlayerSeason(playerId: number | null): Loadable<PlayerSeason> {
  return useResource(async () => {
    if (playerId === null) return null;
    const { data, error } = await api.GET("/api/v1/players/{player_id}/season", {
      params: { path: { player_id: playerId } },
    });
    if (error || !data) return null;
    return data;
  }, [playerId]);
}
