import { useCallback, useEffect, useId, useState } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { PlayerHeadshot } from "./PlayerHeadshot";
import { TeamLogo } from "./TeamLogo";
import { useCombobox } from "./useCombobox";

type Result = components["schemas"]["PlayerSearchResult"];

/** Long enough that a single letter does not fetch the whole league. */
const MIN_QUERY = 2;
const DEBOUNCE_MS = 200;

/**
 * Find a player by name.
 *
 * Replaces the club-then-roster cascade, which required knowing where someone plays
 * before you could look him up — and quietly failed for anyone whose club had changed.
 */
export function PlayerSearch({
  label,
  inputLabel,
  accent,
  selected,
  onSelect,
  dark,
}: {
  label: string;
  /** Accessible name for the box. Defaults to the visible label plus "player", which
   *  reads well for a side ("left player") but not for a label that already says it. */
  inputLabel?: string;
  accent?: string;
  selected: { playerId: number; name: string; teamId: number | null } | null;
  onSelect: (result: Result | null) => void;
  dark: boolean;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Result[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const listId = useId();

  const choose = useCallback(
    (result: Result) => {
      onSelect(result);
      setQuery("");
      setOpen(false);
    },
    [onSelect],
  );
  const dismiss = useCallback(() => setOpen(false), []);
  const { active, setActive, onKeyDown, container } = useCombobox({
    items: results,
    onChoose: choose,
    onDismiss: dismiss,
  });

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < MIN_QUERY) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    // Debounced: typing a name should not be one request per keystroke.
    const timer = window.setTimeout(async () => {
      const { data } = await api.GET("/api/v1/players/search", {
        params: { query: { q: trimmed, limit: 8 } },
      });
      setResults(data?.players ?? []);
      setLoading(false);
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [query]);

  return (
    <div
      ref={container}
      className="relative rounded-md border border-line bg-surface p-2.5"
      style={accent ? { borderLeftColor: accent, borderLeftWidth: 3 } : undefined}
    >
      <div className="mb-1.5 text-xs text-muted">{label}</div>

      {selected ? (
        <div className="flex items-center gap-2">
          <PlayerHeadshot playerId={selected.playerId} name={selected.name} size={26} accent={accent} />
          <span className="min-w-0 flex-1 truncate text-sm text-ink">{selected.name}</span>
          {selected.teamId !== null && <TeamLogo teamId={selected.teamId} dark={dark} size={16} />}
          <button
            onClick={() => onSelect(null)}
            className="shrink-0 rounded border border-line px-1.5 py-0.5 text-[11px] text-muted hover:text-ink"
          >
            change
          </button>
        </div>
      ) : (
        <input
          type="search"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-label={inputLabel ?? `${label} player`}
          placeholder="search by name…"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          aria-activedescendant={
            open && results[active] ? `${listId}-${results[active].player_id}` : undefined
          }
          className="w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink outline-none"
        />
      )}

      {open && !selected && query.trim().length >= MIN_QUERY && (
        <ul
          id={listId}
          role="listbox"
          className="absolute left-0 right-0 top-full z-10 mt-1 max-h-60 overflow-y-auto rounded-md border border-line bg-surface shadow-lg"
        >
          {loading && results.length === 0 && (
            <li className="px-2.5 py-2 text-xs text-faint">searching…</li>
          )}
          {!loading && results.length === 0 && (
            <li className="px-2.5 py-2 text-xs text-faint">no player by that name</li>
          )}
          {results.map((result, index) => (
            <li key={result.player_id}>
              <button
                id={`${listId}-${result.player_id}`}
                role="option"
                aria-selected={index === active}
                onClick={() => choose(result)}
                onMouseEnter={() => setActive(index)}
                className={`flex w-full items-center gap-2 px-2.5 py-1.5 text-left transition-colors ${
                  index === active ? "bg-raised" : "hover:bg-raised"
                }`}
              >
                <PlayerHeadshot playerId={result.player_id} name={result.full_name} size={22} />
                <span className="min-w-0 flex-1 truncate text-[13px] text-ink">
                  {result.full_name}
                </span>
                {result.primary_position && (
                  <span className="shrink-0 font-mono text-[10px] text-faint">
                    {result.primary_position}
                  </span>
                )}
                {result.team_id !== null && result.team_id !== undefined && (
                  <TeamLogo teamId={result.team_id} dark={dark} size={16} />
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
