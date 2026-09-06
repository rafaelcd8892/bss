import { useEffect, useState } from "react";
import { api } from "./api/client";
import type { components } from "./api/schema";

export type RosterPlayer = components["schemas"]["PlayerSummary"];

/** Roster for one club, used to populate a player picker. */
export function useRoster(teamId: number | null): {
  players: RosterPlayer[];
  loading: boolean;
} {
  const [players, setPlayers] = useState<RosterPlayer[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (teamId === null) {
      setPlayers([]);
      return;
    }
    let cancelled = false;
    setLoading(true);

    api
      .GET("/api/v1/teams/{team_id}/roster", { params: { path: { team_id: teamId } } })
      .then(({ data }) => {
        if (cancelled) return;
        setPlayers(data?.players ?? []);
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) {
          setPlayers([]);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [teamId]);

  return { players, loading };
}
