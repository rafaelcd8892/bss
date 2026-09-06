import { teamAccent } from "../teams";
import type { CatalogTeam } from "../useTeamCatalog";

type TeamPickerProps = {
  label: string;
  value: number;
  teams: CatalogTeam[];
  dark: boolean;
  onChange: (teamId: number) => void;
};

export function TeamPicker({ label, value, teams, dark, onChange }: TeamPickerProps) {
  const known = teams.some((team) => team.id === value);

  return (
    <label className="flex min-w-0 flex-col gap-1 text-xs text-muted">
      {label}
      <div className="flex items-center gap-2 rounded-md border border-line bg-surface px-2 py-1.5">
        <span
          className="h-4 w-1.5 shrink-0 rounded-sm"
          style={{ background: teamAccent(value, dark) }}
          aria-hidden
        />
        <select
          value={known ? value : ""}
          onChange={(e) => onChange(Number(e.target.value))}
          className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none"
        >
          {!known && <option value="">Team {value}</option>}
          {teams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </select>
      </div>
    </label>
  );
}
