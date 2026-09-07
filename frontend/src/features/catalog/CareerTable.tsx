import type { components } from "../../api/schema";
import { Card } from "../../components/Card";
import { TeamLogo } from "../../components/TeamLogo";
import { formatMetric, type AnyMetric } from "../analyze/metrics";

type Line = components["schemas"]["PlayerSeasonLine"];
type SeasonLines = components["schemas"]["SeasonLines"];

/** A column reads one field and knows how to render it. */
type Column = {
  key: string;
  label: string;
  /** Rate columns format per metric family; counting columns print as they are. */
  metric?: AnyMetric;
  value: (line: Line) => number | null | undefined;
  title?: string;
};

const HITTING: Column[] = [
  { key: "g", label: "PA", value: (l) => l.plate_appearances },
  { key: "ab", label: "AB", value: (l) => l.at_bats },
  { key: "h", label: "H", value: (l) => l.hits },
  { key: "2b", label: "2B", value: (l) => l.doubles },
  { key: "3b", label: "3B", value: (l) => l.triples },
  { key: "hr", label: "HR", value: (l) => l.home_runs },
  { key: "bb", label: "BB", value: (l) => l.walks },
  { key: "so", label: "SO", value: (l) => l.strikeouts },
  { key: "sb", label: "SB", value: (l) => l.stolen_bases },
  { key: "avg", label: "AVG", metric: "obp", value: (l) => l.batting_average },
  { key: "obp", label: "OBP", metric: "obp", value: (l) => l.obp },
  { key: "slg", label: "SLG", metric: "slg", value: (l) => l.slg },
  { key: "ops", label: "OPS", metric: "ops", value: (l) => l.ops },
  { key: "iso", label: "ISO", metric: "iso", value: (l) => l.iso },
  { key: "woba", label: "wOBA", metric: "woba", value: (l) => l.woba },
  {
    key: "xwoba",
    label: "xwOBA",
    metric: "xwoba",
    value: (l) => l.xwoba,
    title: "Statcast expected wOBA — only for seasons it was ingested for",
  },
  { key: "wrc", label: "wRC+", metric: "wrc_plus", value: (l) => l.wrc_plus },
];

const PITCHING: Column[] = [
  { key: "ip", label: "IP", value: (l) => l.innings_pitched },
  { key: "so", label: "SO", value: (l) => l.strikeouts },
  { key: "bb", label: "BB", value: (l) => l.walks },
  { key: "hr", label: "HR", value: (l) => l.home_runs },
  { key: "era", label: "ERA", metric: "era", value: (l) => l.era },
  { key: "fip", label: "FIP", metric: "fip", value: (l) => l.fip },
  { key: "whip", label: "WHIP", metric: "whip", value: (l) => l.whip },
  { key: "kbb", label: "K/BB", metric: "k_bb_ratio", value: (l) => l.k_bb_ratio },
  { key: "k", label: "K%", metric: "strikeout_rate", value: (l) => l.strikeout_rate },
  { key: "bb%", label: "BB%", metric: "walk_rate", value: (l) => l.walk_rate },
];

function render(column: Column, line: Line): string {
  const value = column.value(line);
  if (value === null || value === undefined) return "—";
  return column.metric ? formatMetric(column.metric, value) : String(value);
}

type Row = { season: number | null; line: Line };

export function CareerTable({
  seasons,
  totals,
  dark,
}: {
  seasons: SeasonLines[];
  totals: Line[];
  dark: boolean;
}) {
  const groups = (["hitting", "pitching"] as const).filter((group) =>
    seasons.some((season) => season.lines.some((line) => line.stat_group === group)),
  );

  if (groups.length === 0) return null;

  return (
    <>
      {groups.map((group) => {
        const columns = group === "hitting" ? HITTING : PITCHING;
        // Oldest first, the way a career is read on a reference page.
        const rows: Row[] = seasons
          .flatMap((season) =>
            season.lines
              .filter((line) => line.stat_group === group)
              .map((line) => ({ season: season.season, line })),
          )
          .sort((a, b) => (a.season ?? 0) - (b.season ?? 0));
        const total = totals.find((line) => line.stat_group === group);

        return (
          <Card key={group} padded={false}>
            <div className="flex items-baseline justify-between gap-2 border-b border-line px-3.5 py-2.5">
              <span className="text-sm font-medium text-ink">
                {group === "hitting" ? "Hitting" : "Pitching"} by season
              </span>
              <span className="text-xs text-faint">
                {rows.length} season{rows.length === 1 ? "" : "s"}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="text-xs text-faint">
                    <th scope="col" className="px-3 py-2 text-left font-normal">
                      season
                    </th>
                    <th scope="col" className="px-2 py-2 text-left font-normal">
                      team
                    </th>
                    {columns.map((column) => (
                      <th
                        key={column.key}
                        scope="col"
                        title={column.title}
                        className="px-2 py-2 text-right font-normal"
                      >
                        {column.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ season, line }) => (
                    <tr key={season} className="border-t border-line">
                      <td className="px-3 py-1.5 font-mono text-xs text-ink">{season}</td>
                      <td className="px-2 py-1.5">
                        {line.team_id ? (
                          <TeamLogo teamId={line.team_id} dark={dark} size={16} />
                        ) : (
                          <span className="text-[10px] text-faint" title="More than one club">
                            multi
                          </span>
                        )}
                      </td>
                      {columns.map((column) => (
                        <td
                          key={column.key}
                          className="px-2 py-1.5 text-right font-mono text-xs text-muted"
                        >
                          {render(column, line)}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {total && rows.length > 1 && (
                    <tr className="border-t-2 border-line-strong bg-raised">
                      <td className="px-3 py-1.5 text-xs font-medium text-ink" colSpan={2}>
                        career
                      </td>
                      {columns.map((column) => (
                        <td
                          key={column.key}
                          className="px-2 py-1.5 text-right font-mono text-xs font-medium text-ink"
                        >
                          {render(column, total)}
                        </td>
                      ))}
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            {total && rows.length > 1 && (
              <p className="border-t border-line px-3.5 py-2 text-[11px] leading-relaxed text-faint">
                Career rates are recomputed from the summed counting stats, not averaged
                across seasons — a ten-at-bat year would otherwise weigh as much as a
                full one. wRC+ and xwOBA are left out of the total on purpose: one is
                league-relative and the league moves, the other is a measurement with no
                denominator to re-weight it by.
              </p>
            )}
          </Card>
        );
      })}
    </>
  );
}
