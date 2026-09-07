import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TeamLogo } from "./TeamLogo";
import { PlayerHeadshot } from "./PlayerHeadshot";

describe("TeamLogo", () => {
  it("renders the club mark", () => {
    const { container } = render(<TeamLogo teamId={147} dark={false} />);
    const image = container.querySelector("img");
    expect(image?.getAttribute("src")).toContain("/147.svg");
  });

  it("falls back to the club's initials when the image fails", () => {
    // The images are third party, so a blocked or broken request must not leave a
    // hole where the club's identity should be.
    const { container } = render(<TeamLogo teamId={147} dark={false} />);
    fireEvent.error(container.querySelector("img")!);
    expect(screen.getByText("NYY")).toBeInTheDocument();
  });

  it("is decorative, so it carries no alt text to read aloud", () => {
    const { container } = render(<TeamLogo teamId={147} dark={false} />);
    expect(container.querySelector("img")?.getAttribute("alt")).toBe("");
  });
});

describe("PlayerHeadshot", () => {
  it("names the player for a screen reader", () => {
    render(<PlayerHeadshot playerId={592450} name="Aaron Judge" />);
    expect(screen.getByAltText("Aaron Judge")).toBeInTheDocument();
  });

  it("falls back to initials when the image fails", () => {
    const { container } = render(<PlayerHeadshot playerId={1} name="Juan Soto" />);
    fireEvent.error(container.querySelector("img")!);
    expect(screen.getByText("JS")).toBeInTheDocument();
  });

  it("handles a single-word name without crashing", () => {
    const { container } = render(<PlayerHeadshot playerId={1} name="Ichiro" />);
    fireEvent.error(container.querySelector("img")!);
    expect(screen.getByText("I")).toBeInTheDocument();
  });
});
