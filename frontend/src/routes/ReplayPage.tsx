import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { Card } from "../components/Card";
import type { GameParams } from "../features/game/url";

type State =
  | { status: "loading" }
  | { status: "found"; params: GameParams }
  | { status: "missing" }
  | { status: "error" };

/**
 * A recorded game, recalled by match id.
 *
 * The stored context *is* the replay: the simulation is deterministic, so handing the
 * saved matchup and seed back to the viewer reproduces the game exactly rather than
 * replaying a cached copy of it.
 */
export function ReplayPage() {
  const { matchId } = useParams();
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    if (!matchId) {
      setState({ status: "missing" });
      return;
    }
    let cancelled = false;

    api
      .GET("/api/v1/games/{match_id}", { params: { path: { match_id: matchId } } })
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error || !data) {
          setState({ status: "missing" });
          return;
        }
        setState({
          status: "found",
          params: {
            homeTeamId: data.home_team_id,
            awayTeamId: data.away_team_id,
            seed: data.context.seed,
            innings: data.innings,
          },
        });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });

    return () => {
      cancelled = true;
    };
  }, [matchId]);

  if (state.status === "found") {
    const { homeTeamId, awayTeamId, seed, innings } = state.params;
    const query = new URLSearchParams({
      home: String(homeTeamId),
      away: String(awayTeamId),
      seed: String(seed),
    });
    if (innings !== 9) query.set("innings", String(innings));
    return <Navigate to={`/game?${query}`} replace />;
  }

  if (state.status === "loading") {
    return (
      <Card className="px-4 py-5">
        <p className="text-sm text-faint">Loading replay…</p>
      </Card>
    );
  }

  return (
    <Card className="px-4 py-5">
      <p className="text-[13px] text-ink">
        {state.status === "missing"
          ? "No recorded game with that id."
          : "Could not reach the API."}
      </p>
      <p className="mt-1.5 text-xs text-muted">
        Recording is opt-in: the API stores runs only when{" "}
        <span className="font-mono">BASEBALL_PERSIST_SIMULATION_RUNS</span> is on.
      </p>
      <Link to="/game" className="mt-2 inline-block text-xs text-muted hover:text-ink">
        Back to the game viewer
      </Link>
    </Card>
  );
}
