import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderRouted } from "../../test/render";
import { PlayersView } from "./PlayersView";

const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }));

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, api: { GET: getMock, POST: vi.fn() } };
});

function row(name: string, overrides: Record<string, unknown> = {}) {
  return {
    player_id: name.length,
    full_name: name,
    primary_position: "RF",
    team_id: 147,
    line: {
      stat_group: "hitting",
      plate_appearances: 600,
      at_bats: 540,
      hits: 150,
      home_runs: 30,
      ops: 0.9,
      era: null,
      ...overrides,
    },
  };
}

/** The query of every table request, newest last. */
function queries(): Record<string, unknown>[] {
  return getMock.mock.calls
    .filter(([path]) => String(path).includes("stats/players"))
    .map(([, options]) => options.params.query);
}

beforeEach(() => {
  getMock.mockReset();
  getMock.mockImplementation((path: string, options?: { params?: { query?: Record<string, unknown> } }) => {
    if (path.includes("stats/seasons")) {
      return Promise.resolve({
        data: [
          { season: 2026, complete: true },
          { season: 2019, complete: false },
        ],
        error: undefined,
      });
    }
    if (path.includes("stats/players")) {
      const query = options?.params?.query ?? {};
      return Promise.resolve({
        data: {
          season: query.season ?? 2026,
          stat_group: query.stat_group ?? "hitting",
          sort: query.sort ?? "pa",
          direction: query.direction ?? "desc",
          total: 120,
          offset: query.offset ?? 0,
          rows: [row("Juan Soto"), row("Aaron Judge", { ops: null })],
        },
        error: undefined,
      });
    }
    return Promise.resolve({ data: { teams: [{ team_id: 147, name: "New York Yankees" }] }, error: undefined });
  });
});

describe("PlayersView", () => {
  it("shows batters by default, sorted by playing time", async () => {
    renderRouted(<PlayersView />, { route: "/analyze/players" });
    await waitFor(() => expect(queries().length).toBeGreaterThan(0));
    expect(queries()[0]).toMatchObject({ stat_group: "hitting", sort: "pa", direction: "desc" });
  });

  it("switches to pitchers, and to a sort that exists for them", async () => {
    // "pa" is meaningless on a pitching table; keeping it would sort by a column the
    // page does not even show.
    renderRouted(<PlayersView />, { route: "/analyze/players" });
    await waitFor(() => expect(screen.getByRole("button", { name: "pitchers" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "pitchers" }));
    await waitFor(() =>
      expect(queries().at(-1)).toMatchObject({ stat_group: "pitching", sort: "ip" }),
    );
  });

  it("drops the direction too when the group changes", async () => {
    // Ascending is right for ERA and wrong for plate appearances. Carrying it across
    // opens the batters table sorted from the least playing time upward.
    renderRouted(<PlayersView />, { route: "/analyze/players?group=pitching&sort=era&dir=asc" });
    await waitFor(() => expect(screen.getByRole("button", { name: "batters" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "batters" }));
    await waitFor(() =>
      expect(queries().at(-1)).toMatchObject({ sort: "pa", direction: "desc" }),
    );
  });

  it("sorts on the server, not over the loaded page", async () => {
    renderRouted(<PlayersView />, { route: "/analyze/players" });
    await waitFor(() => expect(screen.getByRole("button", { name: /HR/ })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /HR/ }));
    await waitFor(() => expect(queries().at(-1)).toMatchObject({ sort: "home_runs" }));
  });

  it("opens a new column best-first, which depends on the metric", async () => {
    renderRouted(<PlayersView />, { route: "/analyze/players?group=pitching" });
    await waitFor(() => expect(screen.getByRole("button", { name: /ERA/ })).toBeInTheDocument());

    // A lower ERA is the better one, so it opens ascending.
    fireEvent.click(screen.getByRole("button", { name: /ERA/ }));
    await waitFor(() =>
      expect(queries().at(-1)).toMatchObject({ sort: "era", direction: "asc" }),
    );
  });

  it("flips the direction when the same column is clicked again", async () => {
    renderRouted(<PlayersView />, { route: "/analyze/players?sort=ops&dir=desc" });
    await waitFor(() => expect(screen.getByRole("button", { name: /OPS/ })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /OPS/ }));
    await waitFor(() => expect(queries().at(-1)).toMatchObject({ direction: "asc" }));
  });

  it("marks the sorted column for a screen reader", async () => {
    renderRouted(<PlayersView />, { route: "/analyze/players?sort=ops&dir=desc" });
    await waitFor(() => expect(screen.getByRole("button", { name: /OPS/ })).toBeInTheDocument());
    const header = screen.getByRole("button", { name: /OPS/ }).closest("th");
    expect(header).toHaveAttribute("aria-sort", "descending");
  });

  it("pages, and starts over when the question changes", async () => {
    // Staying on page three of a different question shows an empty table for no
    // visible reason.
    renderRouted(<PlayersView />, { route: "/analyze/players" });
    await waitFor(() => expect(screen.getByRole("button", { name: "next" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "next" }));
    await waitFor(() => expect(queries().at(-1)).toMatchObject({ offset: 50 }));

    fireEvent.click(screen.getByRole("button", { name: "pitchers" }));
    await waitFor(() => expect(queries().at(-1)).not.toHaveProperty("offset", 50));
  });

  it("sends the club and season filters to the server", async () => {
    renderRouted(<PlayersView />, { route: "/analyze/players" });
    await waitFor(() => expect(screen.getByLabelText(/club/i)).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/club/i), { target: { value: "147" } });
    await waitFor(() => expect(queries().at(-1)).toMatchObject({ team_id: 147 }));

    fireEvent.change(screen.getByLabelText(/season/i), { target: { value: "2019" } });
    await waitFor(() => expect(queries().at(-1)).toMatchObject({ season: 2019 }));
  });

  it("prints a dash where a metric was never ingested", async () => {
    renderRouted(<PlayersView />, { route: "/analyze/players" });
    await waitFor(() => expect(screen.getByText("Aaron Judge")).toBeInTheDocument());

    const judge = screen.getByText("Aaron Judge").closest("tr")!;
    expect(within(judge).getAllByText("—").length).toBeGreaterThan(0);
  });

  it("says how much of the total is on screen", async () => {
    renderRouted(<PlayersView />, { route: "/analyze/players" });
    await waitFor(() => expect(screen.getByText(/of 120/)).toBeInTheDocument());
  });
});
