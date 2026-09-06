import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderRouted } from "../../test/render";
import { CompareView } from "./CompareView";

const { getMock, postMock } = vi.hoisted(() => ({ getMock: vi.fn(), postMock: vi.fn() }));

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, api: { GET: getMock, POST: postMock } };
});

const ROSTER = {
  players: [
    { player_id: 665742, full_name: "Juan Soto", primary_position: "LF" },
    { player_id: 670541, full_name: "Yordan Alvarez", primary_position: "DH" },
  ],
};

function metric(
  left: number,
  right: number,
  leftSource: "real" | "synthetic",
  rightSource: "real" | "synthetic",
  betterId: number,
) {
  return {
    left_value: left,
    right_value: right,
    left_source: leftSource,
    right_source: rightSource,
    delta_left_minus_right: left - right,
    better_player_id: betterId,
    direction: "higher_is_better" as const,
  };
}

const LEFT = 665742;
const RIGHT = 670541;

const COMPARISON = {
  left_player_id: LEFT,
  right_player_id: RIGHT,
  summary: "…",
  metrics: {
    // Measured on both sides: the left player wins one, the right player the other.
    woba: metric(0.388, 0.423, "real", "real", RIGHT),
    wrc_plus: metric(150, 120, "real", "real", LEFT),
    // Seeded: the API still names a "better" player, which must not be believed.
    xwoba: metric(0.293, 0.281, "synthetic", "synthetic", LEFT),
  },
};

beforeEach(() => {
  getMock.mockReset();
  postMock.mockReset();
  getMock.mockImplementation((path: string) =>
    Promise.resolve(
      path.includes("roster")
        ? { data: ROSTER, error: undefined }
        : { data: { teams: [] }, error: undefined },
    ),
  );
  postMock.mockResolvedValue({ data: { result: COMPARISON }, error: undefined });
});

const ROUTE = `/analyze/compare?leftTeam=121&left=${LEFT}&rightTeam=117&right=${RIGHT}`;

describe("CompareView", () => {
  it("counts only measured metrics in the verdict", async () => {
    renderRouted(<CompareView />, { route: ROUTE });

    await waitFor(() =>
      expect(screen.getByText(/measured metric/i)).toBeInTheDocument(),
    );
    // Two measured metrics, one won by the left player. The seeded metric that the
    // API scored in his favour must not inflate this to 2 of 3.
    const verdict = screen.getByText(/measured metric/i).textContent ?? "";
    expect(verdict.replace(/\s+/g, " ")).toContain("leads 1 of 2 measured metrics");
  });

  it("says how many metrics were excluded and why", async () => {
    renderRouted(<CompareView />, { route: ROUTE });
    await waitFor(() =>
      expect(
        screen.getByText(/seeded metric is shown for shape only/i),
      ).toBeInTheDocument(),
    );
  });

  it("labels the seeded metric in the table", async () => {
    renderRouted(<CompareView />, { route: ROUTE });
    await waitFor(() => expect(screen.getByText("xwOBA")).toBeInTheDocument());
    expect(screen.getAllByText("seeded").length).toBe(1);
  });

  it("asks for both players before requesting a comparison", async () => {
    renderRouted(<CompareView />, { route: "/analyze/compare?leftTeam=121&left=665742" });

    await waitFor(() => expect(screen.getByText(/Pick a player on each side/i)).toBeInTheDocument());
    expect(postMock).not.toHaveBeenCalled();
  });

  it("sends the selected players to the API", async () => {
    renderRouted(<CompareView />, { route: ROUTE });

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    expect(postMock.mock.calls[0][1].body).toMatchObject({
      left_player_id: LEFT,
      right_player_id: RIGHT,
    });
  });
});
