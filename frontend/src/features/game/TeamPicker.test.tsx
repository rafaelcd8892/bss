import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CatalogTeam } from "../../useTeamCatalog";
import { TeamPicker } from "./TeamPicker";

const TEAMS: CatalogTeam[] = [
  { id: 147, name: "New York Yankees", abbr: "NYY", primary: "#132448", secondary: "#C4CED3" },
  { id: 121, name: "New York Mets", abbr: "NYM", primary: "#002D72", secondary: "#FF5910" },
  { id: 111, name: "Boston Red Sox", abbr: "BOS", primary: "#BD3039", secondary: "#C4CED4" },
];

function open(): HTMLElement {
  const box = screen.getByRole("combobox");
  fireEvent.focus(box);
  return box;
}

describe("TeamPicker", () => {
  it("shows the chosen club until you start typing", () => {
    render(<TeamPicker label="home" value={147} teams={TEAMS} dark={false} onChange={vi.fn()} />);
    expect(screen.getByRole("combobox")).toHaveValue("New York Yankees");
  });

  it("narrows by abbreviation, which a native select cannot do", () => {
    // Typing "nyy" in a <select> gets you nowhere: it types ahead from the start of the
    // option text, so reaching the Yankees means passing the Mets first.
    render(<TeamPicker label="home" value={147} teams={TEAMS} dark={false} onChange={vi.fn()} />);
    fireEvent.change(open(), { target: { value: "nyy" } });
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(1);
    expect(options[0]).toHaveTextContent("New York Yankees");
  });

  it("narrows by name too", () => {
    render(<TeamPicker label="home" value={147} teams={TEAMS} dark={false} onChange={vi.fn()} />);
    fireEvent.change(open(), { target: { value: "red sox" } });
    expect(screen.getAllByRole("option")).toHaveLength(1);
  });

  it("ignores case", () => {
    render(<TeamPicker label="home" value={147} teams={TEAMS} dark={false} onChange={vi.fn()} />);
    fireEvent.change(open(), { target: { value: "BOS" } });
    expect(screen.getAllByRole("option")).toHaveLength(1);
  });

  it("ignores accents, matching how the player search folds names", () => {
    // No MLB club carries one today, but the fold is shared behaviour and a silently
    // broken character range would only show up the day one did.
    const accented: CatalogTeam[] = [
      { id: 1, name: "Montréal Expos", abbr: "MON", primary: "#000", secondary: "#fff" },
    ];
    render(
      <TeamPicker label="home" value={1} teams={accented} dark={false} onChange={vi.fn()} />,
    );
    fireEvent.change(open(), { target: { value: "montreal" } });
    expect(screen.getAllByRole("option")).toHaveLength(1);
  });

  it("picks with the keyboard", () => {
    const onChange = vi.fn();
    render(<TeamPicker label="home" value={147} teams={TEAMS} dark={false} onChange={onChange} />);
    const box = open();
    fireEvent.keyDown(box, { key: "ArrowDown" });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(121);
  });

  it("picks with the mouse", () => {
    const onChange = vi.fn();
    render(<TeamPicker label="home" value={147} teams={TEAMS} dark={false} onChange={onChange} />);
    open();
    fireEvent.click(within(screen.getByRole("listbox")).getByText("Boston Red Sox"));
    expect(onChange).toHaveBeenCalledWith(111);
  });

  it("says so when nothing matches, rather than showing an empty box", () => {
    render(<TeamPicker label="home" value={147} teams={TEAMS} dark={false} onChange={vi.fn()} />);
    fireEvent.change(open(), { target: { value: "zzz" } });
    expect(screen.getByText(/no club by that name/i)).toBeInTheDocument();
  });

  it("still names a club the catalog has not loaded", () => {
    render(<TeamPicker label="home" value={999} teams={[]} dark={false} onChange={vi.fn()} />);
    expect(screen.getByRole("combobox")).toHaveValue("Team 999");
  });
});
