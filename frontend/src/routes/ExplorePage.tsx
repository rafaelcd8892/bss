import { Placeholder } from "../components/Placeholder";

export function ExplorePage() {
  return (
    <div className="flex flex-col gap-3">
      <Placeholder
        ready
        title="Teams"
        description="Browse the ingested clubs and open a roster. Today these endpoints only
          feed the matchup pickers; here they become a destination of their own."
        endpoint="GET /api/v1/teams · /api/v1/teams/{id}/roster"
      />
      <Placeholder
        ready
        title="Players"
        description="A player page with identity, club and season line, reachable from a
          roster, a leaderboard row or a comparison."
        endpoint="GET /api/v1/players/{id}"
      />
    </div>
  );
}
