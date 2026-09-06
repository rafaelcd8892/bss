import { teamLabel } from "../../teams";

type LineScoreProps = {
  homeTeamId: number;
  awayTeamId: number;
  lineHome: number[];
  lineAway: number[];
  homeScore: number;
  awayScore: number;
  currentInning: number | null;
  homeAccent: string;
  awayAccent: string;
};

export function LineScore({
  homeTeamId,
  awayTeamId,
  lineHome,
  lineAway,
  homeScore,
  awayScore,
  currentInning,
  homeAccent,
  awayAccent,
}: LineScoreProps) {
  const innings = Math.max(lineHome.length, lineAway.length, 9);
  const columns = Array.from({ length: innings }, (_, i) => i);

  return (
    <div className="overflow-x-auto rounded-md border border-line bg-surface px-3 py-2">
      <table className="w-full border-collapse font-mono text-xs">
        <thead>
          <tr className="text-faint">
            <th className="px-1.5 py-0.5 text-left font-normal"></th>
            {columns.map((i) => (
              <th
                key={i}
                className={`px-1.5 py-0.5 text-center font-normal ${
                  currentInning === i + 1 ? "text-ink" : ""
                }`}
              >
                {i + 1}
              </th>
            ))}
            <th className="border-l border-line px-2 py-0.5 text-center font-normal text-muted">
              R
            </th>
          </tr>
        </thead>
        <tbody>
          <Row
            teamId={awayTeamId}
            line={lineAway}
            total={awayScore}
            columns={columns}
            currentInning={currentInning}
            accent={awayAccent}
          />
          <Row
            teamId={homeTeamId}
            line={lineHome}
            total={homeScore}
            columns={columns}
            currentInning={currentInning}
            accent={homeAccent}
          />
        </tbody>
      </table>
    </div>
  );
}

type RowProps = {
  teamId: number;
  line: number[];
  total: number;
  columns: number[];
  currentInning: number | null;
  accent: string;
};

function Row({ teamId, line, total, columns, currentInning, accent }: RowProps) {
  return (
    <tr>
      <td className="px-1.5 py-0.5 text-left">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-1 rounded-sm"
            style={{ background: accent }}
            aria-hidden
          />
          <span className="text-muted">{teamLabel(teamId).abbr}</span>
        </span>
      </td>
      {columns.map((i) => (
        <td
          key={i}
          className={`px-1.5 py-0.5 text-center ${
            currentInning === i + 1 ? "text-ink" : "text-muted"
          }`}
        >
          {i < line.length ? line[i] : <span className="text-faint">·</span>}
        </td>
      ))}
      <td className="border-l border-line px-2 py-0.5 text-center font-medium text-ink">
        {total}
      </td>
    </tr>
  );
}
