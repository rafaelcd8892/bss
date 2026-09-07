import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CareerChart } from "./CareerChart";

type Season = Parameters<typeof CareerChart>[0]["seasons"][number];

function hitting(season: number, woba: number): Season {
  return {
    season,
    lines: [{ stat_group: "hitting", woba, ops: woba + 0.5 }],
  } as unknown as Season;
}

function pitching(season: number, fip: number): Season {
  return { season, lines: [{ stat_group: "pitching", fip }] } as unknown as Season;
}

/** The chart starts collapsed, so every test that inspects it opens it first. */
function open(container: HTMLElement): void {
  fireEvent.click(within(container).getByRole("button", { name: /career chart/i }));
}

describe("CareerChart", () => {
  it("starts collapsed, because the season table says more", () => {
    const { container } = render(
      <CareerChart seasons={[hitting(2025, 0.36), hitting(2026, 0.39)]} accent="#f00" />,
    );
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    open(container);
    expect(screen.getByRole("img")).toBeInTheDocument();
  });

  it("can be put away again", () => {
    const { container } = render(
      <CareerChart seasons={[hitting(2025, 0.36), hitting(2026, 0.39)]} accent="#f00" />,
    );
    open(container);
    open(container);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("says there is no trajectory rather than drawing a flat line", () => {
    render(<CareerChart seasons={[hitting(2026, 0.39)]} accent="#f00" />);
    expect(screen.getByText(/no career to plot yet/i)).toBeInTheDocument();
    expect(screen.getByText(/--history/)).toBeInTheDocument();
  });

  it("plots a season per point, oldest first", () => {
    const { container } = render(
      <CareerChart
        seasons={[hitting(2026, 0.39), hitting(2024, 0.42), hitting(2025, 0.36)]}
        accent="#f00"
      />,
    );
    open(container);
    const chart = screen.getByRole("img");
    expect(chart.getAttribute("aria-label")).toContain("2024 to 2026");
    expect(chart.querySelectorAll("circle")).toHaveLength(3);
  });

  it("marks the best season, not merely the highest number", () => {
    // FIP rewards low values, so the best year is the smallest one.
    const { container } = render(
      <CareerChart seasons={[pitching(2019, 2.33), pitching(2026, 5.65)]} accent="#f00" />,
    );
    open(container);
    expect(screen.getByText("2.33")).toBeInTheDocument();
  });

  it("draws better seasons higher whichever way the metric runs", () => {
    const { container: hittingChart } = render(
      <CareerChart seasons={[hitting(2019, 0.30), hitting(2020, 0.48)]} accent="#f00" />,
    );
    open(hittingChart);
    const [firstUp, secondUp] = [...hittingChart.querySelectorAll("circle")];
    // A better wOBA is a higher point, so a smaller y.
    expect(Number(secondUp.getAttribute("cy"))).toBeLessThan(Number(firstUp.getAttribute("cy")));

    const { container: pitchingChart } = render(
      <CareerChart seasons={[pitching(2019, 5.65), pitching(2020, 2.33)]} accent="#f00" />,
    );
    open(pitchingChart);
    const [firstDown, secondDown] = [...pitchingChart.querySelectorAll("circle")];
    // And so is a better (lower) FIP.
    expect(Number(secondDown.getAttribute("cy"))).toBeLessThan(
      Number(firstDown.getAttribute("cy")),
    );
  });

  it("offers only the metrics that belong to the stat group", () => {
    const { container } = render(
      <CareerChart seasons={[pitching(2025, 3.1), pitching(2026, 4.2)]} accent="#f00" />,
    );
    open(container);
    expect(screen.getByRole("button", { name: "ERA" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "OPS" })).not.toBeInTheDocument();
  });

  it("says so when the chosen metric was never ingested", () => {
    const seasons = [
      { season: 2025, lines: [{ stat_group: "hitting", woba: null }] },
      { season: 2026, lines: [{ stat_group: "hitting", woba: null }] },
    ] as unknown as Season[];
    const { container } = render(<CareerChart seasons={seasons} accent="#f00" />);
    open(container);
    expect(
      screen.getByText(/No wOBA recorded across enough seasons/i),
    ).toBeInTheDocument();
  });

  it("names each point for a reader who hovers", () => {
    const { container } = render(
      <CareerChart seasons={[hitting(2025, 0.36), hitting(2026, 0.39)]} accent="#f00" />,
    );
    open(container);
    const chart = screen.getByRole("img");
    expect(within(chart).getByText("2026: .390")).toBeInTheDocument();
  });
});
