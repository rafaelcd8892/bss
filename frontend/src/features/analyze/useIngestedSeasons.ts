import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/schema";

export type IngestedSeason = components["schemas"]["IngestedSeason"];

/**
 * Seasons with ingested stats, newest first.
 *
 * Each says whether it holds the whole league or only the careers of players a club
 * rosters today — a difference invisible in the numbers, so a caller showing a past
 * season has to be told which it is.
 *
 * Empty until the request lands, and empty for good on a database that has never been
 * backfilled — callers should treat "one season or none" as "do not offer a choice".
 */
export function useIngestedSeasons(): IngestedSeason[] {
  const [seasons, setSeasons] = useState<IngestedSeason[]>([]);

  useEffect(() => {
    let cancelled = false;
    api.GET("/api/v1/stats/seasons", {}).then(({ data }) => {
      if (!cancelled && Array.isArray(data)) setSeasons(data);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return seasons;
}
