import { useEffect, useState } from "react";
import { api, type LeaderMetric, type StatLeadersResult } from "../../api/client";

export type LeadersQuery = {
  metric: LeaderMetric;
  limit: number;
  /** null means "let the server apply its default qualifier". */
  minimum: number | null;
  /** null is the whole league. */
  teamId: number | null;
  /** null is the configured season. */
  season: number | null;
};

export type LeadersState = {
  data: StatLeadersResult | null;
  loading: boolean;
  error: string | null;
};

export function useLeaders({
  metric,
  limit,
  minimum,
  teamId,
  season,
}: LeadersQuery): LeadersState {
  const [state, setState] = useState<LeadersState>({
    data: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState((previous) => ({ ...previous, loading: true, error: null }));

    api
      .GET("/api/v1/stats/leaders", {
        params: {
          query: {
            metric,
            limit,
            ...(minimum !== null ? { minimum } : {}),
            ...(teamId !== null ? { team_id: teamId } : {}),
            ...(season !== null ? { season } : {}),
          },
        },
      })
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error || !data) {
          setState({
            data: null,
            loading: false,
            error:
              "Could not load leaders. The API needs a database with ingested season stats.",
          });
          return;
        }
        setState({ data, loading: false, error: null });
      })
      .catch(() => {
        if (!cancelled) {
          setState({ data: null, loading: false, error: "Could not reach the API." });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [metric, limit, minimum, teamId, season]);

  return state;
}
