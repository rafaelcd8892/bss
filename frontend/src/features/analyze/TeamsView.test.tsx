import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderRouted } from "../../test/render";
import { TeamsView } from "./TeamsView";

const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }));

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, api: { GET: getMock, POST: vi.fn() } };
});

function factors(offense: number, prevention: number) {
  return {
    offense,
    discipline: 0.5,
    power: 0.5,
    speed: 0.5,
    prevention,
    command: 0.5,
    range_factor: 0.5,
  };
}

const TEAMS = [
  // LAD: best pitching. NYY: best offense. NYM: no pitching ingested at all.
  { team_id: 119, season: 2026, source: "real", factors: factors(0.4, 0.9),
    team_woba: 0.331, team_fip: 3.29, batters_counted: 16, pitchers_counted: 14 },
  { team_id: 147, season: 2026, source: "real", factors: factors(0.8, 0.5),
    team_woba: 0.312, team_fip: 4.5, batters_counted: 14, pitchers_counted: 12 },
  { team_id: 121, season: 2026, source: "real", factors: factors(0.6, 0.5),
    team_woba: 0.311, team_fip: null, batters_counted: 14, pitchers_counted: 0 },
];

beforeEach(() => {
  getMock.mockReset();
  getMock.mockResolvedValue({ data: { season: 2026, teams: TEAMS }, error: undefined });
});

function teamOrder(): string[] {
  return screen
    .getAllByRole("row")
    .slice(1) // drop the header row
    .map((row) => within(row).getAllByRole("cell")[0].textContent?.trim() ?? "");
}

describe("TeamsView", () => {
  it("opens sorted by offense, best first", async () => {
    renderRouted(<TeamsView />);
    await waitFor(() => expect(screen.getByText(/30 clubs|3 clubs/)).toBeInTheDocument());
    expect(teamOrder()).toEqual(["NYY", "NYM", "LAD"]);
  });

  it("sorts FIP ascending on first click, because lower is better there", async () => {
    renderRouted(<TeamsView />);
    await waitFor(() => expect(screen.getByText("LAD")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle(/Aggregate team FIP/));

    await waitFor(() => {
      // Best staff first, and the club with no ingested FIP sorts last.
      expect(teamOrder()).toEqual(["LAD", "NYY", "NYM"]);
    });
  });

  it("keeps clubs without a value last when the sort is flipped", async () => {
    renderRouted(<TeamsView />);
    await waitFor(() => expect(screen.getByText("LAD")).toBeInTheDocument());

    const header = screen.getByTitle(/Aggregate team FIP/);
    fireEvent.click(header); // ascending, best first
    await waitFor(() => expect(teamOrder()[0]).toBe("LAD"));

    fireEvent.click(header); // descending, worst first
    await waitFor(() => {
      const order = teamOrder();
      expect(order[0]).toBe("NYY");
      // NYM has no FIP: it must not float to the top just because we reversed.
      expect(order[order.length - 1]).toBe("NYM");
    });
  });

  it("explains why fielding range is absent instead of showing a constant column", async () => {
    renderRouted(<TeamsView />);
    await waitFor(() => expect(screen.getByText("LAD")).toBeInTheDocument());
    expect(screen.queryByTitle(/fielding range/i)).not.toBeInTheDocument();
    expect(screen.getByText(/fielding data is not ingested yet/i)).toBeInTheDocument();
  });

  it("surfaces a real failure instead of an empty table", async () => {
    getMock.mockResolvedValue({ data: undefined, error: { detail: "boom" } });
    renderRouted(<TeamsView />);
    await waitFor(() =>
      expect(screen.getByText(/Could not load team profiles/i)).toBeInTheDocument(),
    );
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
