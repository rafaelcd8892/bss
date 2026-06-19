import { teamLabel } from "../teams";

type LineScoreProps = {
  homeTeamId: number;
  awayTeamId: number;
  lineHome: number[];
  lineAway: number[];
  homeScore: number;
  awayScore: number;
};

export function LineScore({
  homeTeamId,
  awayTeamId,
  lineHome,
  lineAway,
  homeScore,
  awayScore,
}: LineScoreProps) {
  const innings = Math.max(lineHome.length, lineAway.length, 9);
  const columns = Array.from({ length: innings }, (_, i) => i);

  return (
    <div className="overflow-x-auto rounded-md border border-neutral-200 bg-white px-3 py-2">
      <table className="w-full border-collapse font-mono text-xs">
        <thead>
          <tr className="text-neutral-400">
            <th className="px-1.5 py-0.5 text-left font-normal"></th>
            {columns.map((i) => (
              <th key={i} className="px-1.5 py-0.5 text-center font-normal">
                {i + 1}
              </th>
            ))}
            <th className="border-l border-neutral-200 px-2 py-0.5 text-center font-normal text-neutral-600">
              R
            </th>
          </tr>
        </thead>
        <tbody>
          <Row label={teamLabel(awayTeamId).abbr} line={lineAway} total={awayScore} columns={columns} />
          <Row label={teamLabel(homeTeamId).abbr} line={lineHome} total={homeScore} columns={columns} />
        </tbody>
      </table>
    </div>
  );
}

type RowProps = {
  label: string;
  line: number[];
  total: number;
  columns: number[];
};

function Row({ label, line, total, columns }: RowProps) {
  return (
    <tr>
      <td className="px-1.5 py-0.5 text-left text-neutral-500">{label}</td>
      {columns.map((i) => (
        <td key={i} className="px-1.5 py-0.5 text-center">
          {i < line.length ? line[i] : <span className="text-neutral-300">·</span>}
        </td>
      ))}
      <td className="border-l border-neutral-200 px-2 py-0.5 text-center font-medium">{total}</td>
    </tr>
  );
}
