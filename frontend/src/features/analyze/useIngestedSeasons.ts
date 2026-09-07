import { useEffect, useState } from "react";
import { api } from "../../api/client";

/**
 * Seasons with ingested stats, newest first.
 *
 * Empty until the request lands, and empty for good on a database that has never been
 * backfilled — callers should treat "one season or none" as "do not offer a choice".
 */
export function useIngestedSeasons(): number[] {
  const [seasons, setSeasons] = useState<number[]>([]);

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
