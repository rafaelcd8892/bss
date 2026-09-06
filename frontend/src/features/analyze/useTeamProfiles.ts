import { useEffect, useState } from "react";
import { api, type TeamProfile } from "../../api/client";

export type TeamProfilesState = {
  teams: TeamProfile[];
  season: number | null;
  loading: boolean;
  error: string | null;
};

/** Every club's profile for a season, in one request. */
export function useTeamProfiles(): TeamProfilesState {
  const [state, setState] = useState<TeamProfilesState>({
    teams: [],
    season: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    api
      .GET("/api/v1/stats/teams", {})
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error || !data) {
          setState({
            teams: [],
            season: null,
            loading: false,
            error:
              "Could not load team profiles. The API needs a database with ingested season stats.",
          });
          return;
        }
        setState({ teams: data.teams, season: data.season, loading: false, error: null });
      })
      .catch(() => {
        if (!cancelled) {
          setState({
            teams: [],
            season: null,
            loading: false,
            error: "Could not reach the API.",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
