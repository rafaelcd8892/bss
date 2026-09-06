import { useEffect, useState } from "react";
import { api, type ComparePlayersResult } from "../../api/client";

export type CompareState = {
  data: ComparePlayersResult | null;
  loading: boolean;
  error: string | null;
};

export function usePlayerCompare(
  left: number | null,
  right: number | null,
  seed: number,
): CompareState {
  const [state, setState] = useState<CompareState>({
    data: null,
    loading: false,
    error: null,
  });

  useEffect(() => {
    if (left === null || right === null) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    let cancelled = false;
    setState((previous) => ({ ...previous, loading: true, error: null }));

    api
      .POST("/api/v1/compare/players", {
        body: {
          left_player_id: left,
          right_player_id: right,
          context: {
            seed,
            model_version: "baseline-v1",
            data_snapshot_id: "ui",
          },
        },
      })
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error || !data) {
          setState({ data: null, loading: false, error: "Could not load the comparison." });
          return;
        }
        setState({ data: data.result, loading: false, error: null });
      })
      .catch(() => {
        if (!cancelled) {
          setState({ data: null, loading: false, error: "Could not reach the API." });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [left, right, seed]);

  return state;
}
