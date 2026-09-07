import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CareerTable } from "./CareerTable";

type Props = Parameters<typeof CareerTable>[0];
type Season = Props["seasons"][number];
type Line = Props["totals"][number];

function hittingSeason(season: number, teamId: number | null, overrides = {}): Season {
  return {
    season,
    lines: [
      {
        stat_group: "hitting",
        team_id: teamId,
        plate_appearances: 600,
        at_bats: 540,
        hits: 150,
        home_runs: 25,
        batting_average: 0.278,
        ops: 0.845,
        ...overrides,
      },
    ],
  } as unknown as Season;
}

const TOTAL = {
  stat_group: "hitting",
  plate_appearances: 1200,
  at_bats: 1080,
  hits: 300,
  home_runs: 50,
  batting_average: 0.278,
  ops: 0.845,
} as unknown as Line;

function rowFor(label: string): HTMLElement {
  const row = screen
    .getAllByRole("row")
    .find((candidate) => within(candidate).queryAllByRole("cell")[0]?.textContent === label);
  if (!row) throw new Error(`no row for ${label}`);
  return row;
}

describe("CareerTable", () => {
  it("lists seasons oldest first, the way a reference page reads", () => {
    render(
      <CareerTable
        seasons={[hittingSeason(2026, 147), hittingSeason(2024, 147), hittingSeason(2025, 147)]}
        totals={[TOTAL]}
        dark={false}
      />,
    );
    const seasons = screen
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).queryAllByRole("cell")[0]?.textContent);
    expect(seasons.slice(0, 3)).toEqual(["2024", "2025", "2026"]);
  });

  it("shows the career totals the server computed, not a client-side sum", () => {
    render(
      <CareerTable
        seasons={[hittingSeason(2025, 147), hittingSeason(2026, 147)]}
        totals={[TOTAL]}
        dark={false}
      />,
    );
    const career = rowFor("career");
    expect(within(career).getByText("1200")).toBeInTheDocument();
    // Recomputed from the sum, so it is not double the season's rate.
    expect(within(career).getByText(".278")).toBeInTheDocument();
  });

  it("says a traded season was split across clubs rather than picking one", () => {
    render(
      <CareerTable seasons={[hittingSeason(2022, null)]} totals={[TOTAL]} dark={false} />,
    );
    expect(screen.getByText("multi")).toBeInTheDocument();
  });

  it("omits the career row for a single season, where it would just repeat it", () => {
    render(
      <CareerTable seasons={[hittingSeason(2026, 147)]} totals={[TOTAL]} dark={false} />,
    );
    expect(screen.queryByText("career")).not.toBeInTheDocument();
  });

  it("explains why the career rates are not averages", () => {
    render(
      <CareerTable
        seasons={[hittingSeason(2025, 147), hittingSeason(2026, 147)]}
        totals={[TOTAL]}
        dark={false}
      />,
    );
    expect(screen.getByText(/not averaged across seasons/i)).toBeInTheDocument();
  });

  it("renders a table per stat group a two-way player has", () => {
    const twoWay = {
      season: 2026,
      lines: [
        { stat_group: "hitting", team_id: 147, plate_appearances: 600 },
        { stat_group: "pitching", team_id: 147, innings_pitched: 130 },
      ],
    } as unknown as Season;
    render(<CareerTable seasons={[twoWay]} totals={[]} dark={false} />);
    expect(screen.getByText(/Hitting by season/)).toBeInTheDocument();
    expect(screen.getByText(/Pitching by season/)).toBeInTheDocument();
  });

  it("renders nothing at all when no season carries a line", () => {
    const { container } = render(<CareerTable seasons={[]} totals={[]} dark={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("prints a dash where a metric was never ingested", () => {
    render(
      <CareerTable
        seasons={[
          hittingSeason(2025, 147, { ops: null }),
          hittingSeason(2026, 147, { ops: null }),
        ]}
        totals={[TOTAL]}
        dark={false}
      />,
    );
    expect(within(rowFor("2025")).getAllByText("—").length).toBeGreaterThan(0);
  });
});
