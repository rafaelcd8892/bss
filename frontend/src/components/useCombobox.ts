import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Keyboard and dismissal behaviour shared by the search controls.
 *
 * A native `<select>` gives arrow keys, Enter, Escape and type-ahead for free. Anything
 * that replaces one has to earn that back, or it is a downgrade dressed as an
 * improvement — so this exists to keep both comboboxes honest rather than to save
 * typing.
 */
export function useCombobox<T>({
  items,
  onChoose,
  onDismiss,
}: {
  items: T[];
  onChoose: (item: T) => void;
  onDismiss?: () => void;
}) {
  const [active, setActive] = useState(0);
  const container = useRef<HTMLDivElement>(null);

  // A new result set invalidates the old highlight; keeping it would move the
  // selection to whatever happens to sit at that index now.
  useEffect(() => setActive(0), [items]);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (container.current && !container.current.contains(event.target as Node)) {
        onDismiss?.();
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [onDismiss]);

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        if (items.length === 0) return;
        const step = event.key === "ArrowDown" ? 1 : -1;
        // Wraps, like a native select's list does at either end.
        setActive((current) => (current + step + items.length) % items.length);
      } else if (event.key === "Enter") {
        const item = items[active];
        if (item !== undefined) {
          event.preventDefault();
          onChoose(item);
        }
      } else if (event.key === "Escape") {
        event.preventDefault();
        onDismiss?.();
      }
    },
    [items, active, onChoose, onDismiss],
  );

  return { active, setActive, onKeyDown, container };
}
