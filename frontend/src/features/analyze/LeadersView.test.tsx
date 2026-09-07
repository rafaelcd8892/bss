import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderRouted } from "../../test/render";
import { LeadersView } from "./LeadersView";

const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }));

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, api: { GET: getMock, POST: vi.fn() } };
});

const TEAMS = [
  { team_id: 147, name: "New York Yankees", abbreviation: "NYY" },
  { team_id: 121, name: "New York Mets", abbreviation: "NYM" },
];

function board(season: number, teamId: number | null) {
  return {
    metric: "woba",
    season,
    team_id: teamId,
    direction: "higher_is_better",
    qualifier: "min 200 PA",
    leaders: [
      {
        rank: 1,
        player_id: 1,
        full_name: "Juan Soto",
        team_id: teamId ?? 121,
        value: 0.389,
        plate_appearances: 600,
        innings_pitched: null,
      },
    ],
  };
}

/** Every leaders request the view made, newest last. */
function leaderQueries(): Record<string, unknown>[] {
  return getMock.mock.calls
    .filter(([path]) => String(path).includes("stats/leaders"))
    .map(([, options]) => options.params.query);
}

beforeEach(() => {
  getMock.mockReset();
  getMock.mockImplementation((path: string, options?: { params?: { query?: Record<string, number> } }) => {
    if (path.includes("stats/seasons")) {
      return Promise.resolve({ data: [2026, 2025, 2019], error: undefined });
    }
    if (path.includes("stats/leaders")) {
      const query = options?.params?.query ?? {};
      return Promise.resolve({
        data: board(query.season ?? 2026, query.team_id ?? null),
        error: undefined,
      });
    }
    return Promise.resolve({ data: { teams: TEAMS }, error: undefined });
  });
});

describe("LeadersView filters", () => {
  it("asks for the whole league by default", async () => {
    renderRouted(<LeadersView />, { route: "/analyze/leaders" });
    await waitFor(() => expect(leaderQueries().length).toBeGreaterThan(0));
    expect(leaderQueries()[0]).not.toHaveProperty("team_id");
  });

  it("narrows to the chosen club", async () => {
    renderRouted(<LeadersView />, { route: "/analyze/leaders" });
    await waitFor(() => expect(screen.getByLabelText(/club/i)).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/club/i), { target: { value: "147" } });
    await waitFor(() => expect(leaderQueries().at(-1)).toMatchObject({ team_id: 147 }));
  });

  it("reads a club straight off the URL, so a board is shareable", async () => {
    renderRouted(<LeadersView />, { route: "/analyze/leaders?team=121" });
    await waitFor(() => expect(leaderQueries()[0]).toMatchObject({ team_id: 121 }));
  });

  it("goes back to the whole league when the club is cleared", async () => {
    renderRouted(<LeadersView />, { route: "/analyze/leaders?team=121" });
    await waitFor(() => expect(screen.getByLabelText(/club/i)).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/club/i), { target: { value: "" } });
    await waitFor(() => expect(leaderQueries().at(-1)).not.toHaveProperty("team_id"));
  });

  it("offers the ingested seasons and asks for the chosen one", async () => {
    renderRouted(<LeadersView />, { route: "/analyze/leaders" });
    await waitFor(() => expect(screen.getByLabelText(/season/i)).toBeInTheDocument());

    const picker = screen.getByLabelText(/season/i) as HTMLSelectElement;
    expect([...picker.options].map((option) => option.value)).toEqual(["2026", "2025", "2019"]);

    fireEvent.change(picker, { target: { value: "2019" } });
    await waitFor(() => expect(leaderQueries().at(-1)).toMatchObject({ season: 2019 }));
  });

  it("warns that a past season only ranks players still on a roster", async () => {
    // The backfill follows current players' careers, so a 2019 board is missing
    // everyone who has since retired. Presenting it as that year's leaderboard would
    // be wrong in a way nobody could see from the numbers.
    renderRouted(<LeadersView />, { route: "/analyze/leaders?season=2019" });
    await waitFor(() =>
      expect(screen.getByText(/not as that year's leaderboard/i)).toBeInTheDocument(),
    );
  });

  it("does not warn on the current season, where nothing is missing", async () => {
    renderRouted(<LeadersView />, { route: "/analyze/leaders" });
    await waitFor(() => expect(screen.getByText(/Juan Soto/)).toBeInTheDocument());
    expect(screen.queryByText(/not as that year's leaderboard/i)).not.toBeInTheDocument();
  });
});
