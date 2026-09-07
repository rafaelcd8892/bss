import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useCombobox } from "./useCombobox";

/**
 * A native `<select>` gives arrow keys, Enter and Escape for free. These controls
 * replace one, so they have to earn that behaviour back — without it the change is a
 * downgrade dressed as an improvement.
 */
function Harness({
  items,
  onChoose,
  onDismiss,
}: {
  items: string[];
  onChoose: (item: string) => void;
  onDismiss?: () => void;
}) {
  const { active, onKeyDown, container } = useCombobox({ items, onChoose, onDismiss });
  return (
    <div ref={container}>
      <input aria-label="box" onKeyDown={onKeyDown} />
      <ul>
        {items.map((item, index) => (
          <li key={item} data-active={index === active}>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

const ITEMS = ["Yankees", "Mets", "Dodgers"];

function activeItem(): string | null {
  return document.querySelector('[data-active="true"]')?.textContent ?? null;
}

describe("useCombobox", () => {
  it("starts on the first item", () => {
    render(<Harness items={ITEMS} onChoose={vi.fn()} />);
    expect(activeItem()).toBe("Yankees");
  });

  it("moves with the arrow keys", () => {
    render(<Harness items={ITEMS} onChoose={vi.fn()} />);
    fireEvent.keyDown(screen.getByLabelText("box"), { key: "ArrowDown" });
    expect(activeItem()).toBe("Mets");
    fireEvent.keyDown(screen.getByLabelText("box"), { key: "ArrowUp" });
    expect(activeItem()).toBe("Yankees");
  });

  it("wraps at both ends, the way a list does", () => {
    render(<Harness items={ITEMS} onChoose={vi.fn()} />);
    fireEvent.keyDown(screen.getByLabelText("box"), { key: "ArrowUp" });
    expect(activeItem()).toBe("Dodgers");
    fireEvent.keyDown(screen.getByLabelText("box"), { key: "ArrowDown" });
    expect(activeItem()).toBe("Yankees");
  });

  it("chooses the highlighted item on Enter", () => {
    const onChoose = vi.fn();
    render(<Harness items={ITEMS} onChoose={onChoose} />);
    fireEvent.keyDown(screen.getByLabelText("box"), { key: "ArrowDown" });
    fireEvent.keyDown(screen.getByLabelText("box"), { key: "Enter" });
    expect(onChoose).toHaveBeenCalledWith("Mets");
  });

  it("dismisses on Escape", () => {
    const onDismiss = vi.fn();
    render(<Harness items={ITEMS} onChoose={vi.fn()} onDismiss={onDismiss} />);
    fireEvent.keyDown(screen.getByLabelText("box"), { key: "Escape" });
    expect(onDismiss).toHaveBeenCalled();
  });

  it("dismisses on a click outside, not inside", () => {
    const onDismiss = vi.fn();
    render(<Harness items={ITEMS} onChoose={vi.fn()} onDismiss={onDismiss} />);
    fireEvent.mouseDown(screen.getByLabelText("box"));
    expect(onDismiss).not.toHaveBeenCalled();
    fireEvent.mouseDown(document.body);
    expect(onDismiss).toHaveBeenCalled();
  });

  it("does nothing on Enter with nothing to choose", () => {
    const onChoose = vi.fn();
    render(<Harness items={[]} onChoose={onChoose} />);
    fireEvent.keyDown(screen.getByLabelText("box"), { key: "Enter" });
    expect(onChoose).not.toHaveBeenCalled();
  });

  it("resets the highlight when the results change", () => {
    // Otherwise Enter picks whatever now sits at the old index — a different player
    // from the one the user was looking at.
    const { rerender } = render(<Harness items={ITEMS} onChoose={vi.fn()} />);
    fireEvent.keyDown(screen.getByLabelText("box"), { key: "ArrowDown" });
    expect(activeItem()).toBe("Mets");
    rerender(<Harness items={["Padres", "Giants"]} onChoose={vi.fn()} />);
    expect(activeItem()).toBe("Padres");
  });
});
