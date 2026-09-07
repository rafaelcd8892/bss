import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/schema";

export type PlayerTable = components["schemas"]["PlayerStatsTableResponse"];
/** Derived from the response rather than a named schema: a bare Literal alias is
 *  inlined by the generator, so this is the one place the union is spelled. */
export type TableSort = PlayerTable["sort"];

export type PlayerTableQuery = {
  statGroup: "hitting" | "pitching";
  sort: TableSort;
  direction: "asc" | "desc";
  season: number | null;
  teamId: number | null;
  search: string;
  minimum: number | null;
  limit: number;
  offset: number;
};

export type PlayerTableState = {
  data: PlayerTable | null;
  loading: boolean;
  error: string | null;
};

export function usePlayerTable(query: PlayerTableQuery): PlayerTableState {
  const [state, setState] = useState<PlayerTableState>({
    data: null,
    loading: true,
    error: null,
  });
  const { statGroup, sort, direction, season, teamId, search, minimum, limit, offset } = query;

  useEffect(() => {
    let cancelled = false;
    setState((previous) => ({ ...previous, loading: true, error: null }));

    api
      .GET("/api/v1/stats/players", {
        params: {
          query: {
            stat_group: statGroup,
            sort,
            direction,
            limit,
            offset,
            ...(season !== null ? { season } : {}),
            ...(teamId !== null ? { team_id: teamId } : {}),
            ...(search ? { q: search } : {}),
            ...(minimum !== null ? { minimum } : {}),
          },
        },
      })
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error || !data) {
          setState({ data: null, loading: false, error: "Could not load the table." });
          return;
        }
        setState({ data, loading: false, error: null });
      })
      .catch(() => {
        if (!cancelled) setState({ data: null, loading: false, error: "Could not reach the API." });
      });

    return () => {
      cancelled = true;
    };
  }, [statGroup, sort, direction, season, teamId, search, minimum, limit, offset]);

  return state;
}
