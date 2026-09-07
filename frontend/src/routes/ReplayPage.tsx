import { useEffect, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { ShellContext } from "../components/AppShell";
import { Card } from "../components/Card";
import { GameViewer, type ReplayContext } from "../features/game/GameViewer";

type State =
  | { status: "loading" }
  | { status: "found"; replay: ReplayContext }
  | { status: "missing" }
  | { status: "unfaithful" }
  | { status: "error" };

/**
 * A recorded game, recalled by match id.
 *
 * The server replays it under the ruleset stored with the run, so retuning the model
 * cannot change what an old link shows (ADR-028). Handing the matchup back to the
 * normal simulate endpoint would instead play it under today's rules while still
 * calling it the original — which is why this fetches the replay rather than the
 * matchup.
 */
export function ReplayPage() {
  const { dark } = useOutletContext<ShellContext>();
  const { matchId } = useParams();
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    if (!matchId) {
      setState({ status: "missing" });
      return;
    }
    let cancelled = false;

    async function load(id: string) {
      const run = await api.GET("/api/v1/games/{match_id}", {
        params: { path: { match_id: id } },
      });
      if (cancelled) return;
      if (run.error || !run.data) {
        setState({ status: "missing" });
        return;
      }
      const replayed = await api.GET("/api/v1/games/{match_id}/play-by-play", {
        params: { path: { match_id: id } },
      });
      if (cancelled) return;
      if (replayed.error || !replayed.data) {
        // The run predates stored rulesets, so it cannot be replayed faithfully. The
        // server refuses rather than guessing, and so does the page.
        setState({ status: "unfaithful" });
        return;
      }
      setState({
        status: "found",
        replay: {
          matchId: id,
          rulesetId: run.data.ruleset_id ?? null,
          seed: run.data.context.seed,
          result: replayed.data.result,
        },
      });
    }

    void load(matchId).catch(() => {
      if (!cancelled) setState({ status: "error" });
    });

    return () => {
      cancelled = true;
    };
  }, [matchId]);

  if (state.status === "found") {
    return <GameViewer dark={dark} replay={state.replay} />;
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
          : state.status === "unfaithful"
            ? "This game was recorded before its rules were stored with it."
            : "Could not reach the API."}
      </p>
      <p className="mt-1.5 text-xs text-muted">
        {state.status === "unfaithful" ? (
          <>
            Replaying it now would use the current ruleset, which is not the one it was
            played under — so it would be a different game wearing the same id.
          </>
        ) : (
          <>
            Recording is opt-in: the API stores runs only when{" "}
            <span className="font-mono">BASEBALL_PERSIST_SIMULATION_RUNS</span> is on.
          </>
        )}
      </p>
      <Link to="/game" className="mt-2 inline-block text-xs text-muted hover:text-ink">
        Back to the game viewer
      </Link>
    </Card>
  );
}
