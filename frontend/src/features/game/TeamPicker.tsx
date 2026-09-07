import { useCallback, useId, useMemo, useState } from "react";
import { TeamLogo } from "../../components/TeamLogo";
import { useCombobox } from "../../components/useCombobox";
import { teamAccent, teamLabel } from "../../teams";
import type { CatalogTeam } from "../../useTeamCatalog";

type TeamPickerProps = {
  label: string;
  value: number;
  teams: CatalogTeam[];
  dark: boolean;
  onChange: (teamId: number) => void;
};

/** Fold the way the search endpoint does, so "sox" and "SOX" both narrow the list. */
function fold(value: string): string {
  // Escapes rather than literal combining marks, which are invisible in source.
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

/**
 * Pick a club by typing, not by scanning thirty options.
 *
 * A native `<select>` types-ahead from the start of the option text, so reaching the
 * Yankees means typing "new york y" and passing the Mets on the way. Matching the
 * abbreviation as well makes "nyy" enough. Replacing a native control means owning its
 * keyboard behaviour, which `useCombobox` provides.
 */
export function TeamPicker({ label, value, teams, dark, onChange }: TeamPickerProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const listId = useId();
  const selected = teams.find((team) => team.id === value);

  const matches = useMemo(() => {
    const needle = fold(query.trim());
    if (!needle) return teams;
    return teams.filter((team) => {
      const abbr = team.abbr ?? teamLabel(team.id).abbr;
      return fold(team.name).includes(needle) || fold(abbr).includes(needle);
    });
  }, [teams, query]);

  const choose = useCallback(
    (team: CatalogTeam) => {
      onChange(team.id);
      setQuery("");
      setOpen(false);
    },
    [onChange],
  );
  const dismiss = useCallback(() => {
    setQuery("");
    setOpen(false);
  }, []);
  const { active, setActive, onKeyDown, container } = useCombobox({
    items: matches,
    onChoose: choose,
    onDismiss: dismiss,
  });

  return (
    <div ref={container} className="relative flex min-w-0 flex-col gap-1 text-xs text-muted">
      <label htmlFor={`${listId}-input`}>{label}</label>
      <div className="flex items-center gap-2 rounded-md border border-line bg-surface px-2 py-1.5">
        <span
          className="h-4 w-1.5 shrink-0 rounded-sm"
          style={{ background: teamAccent(value, dark) }}
          aria-hidden
        />
        <TeamLogo teamId={value} dark={dark} size={18} />
        <input
          id={`${listId}-input`}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={
            open && matches[active] ? `${listId}-${matches[active].id}` : undefined
          }
          value={open ? query : (selected?.name ?? `Team ${value}`)}
          placeholder="name or abbreviation…"
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
          className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none"
        />
      </div>

      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute left-0 right-0 top-full z-10 mt-1 max-h-64 overflow-y-auto rounded-md border border-line bg-surface shadow-lg"
        >
          {matches.length === 0 && (
            <li className="px-2.5 py-2 text-xs text-faint">no club by that name</li>
          )}
          {matches.map((team, index) => (
            <li key={team.id}>
              <button
                id={`${listId}-${team.id}`}
                role="option"
                aria-selected={index === active}
                onClick={() => choose(team)}
                onMouseEnter={() => setActive(index)}
                className={`flex w-full items-center gap-2 px-2.5 py-1.5 text-left transition-colors ${
                  index === active ? "bg-raised" : "hover:bg-raised"
                }`}
              >
                <TeamLogo teamId={team.id} dark={dark} size={16} />
                <span className="min-w-0 flex-1 truncate text-[13px] text-ink">{team.name}</span>
                <span className="shrink-0 font-mono text-[10px] text-faint">
                  {team.abbr ?? teamLabel(team.id).abbr}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
