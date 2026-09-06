import { teamLabel } from "../../teams";

type WinProbabilityProps = {
  homeTeamId: number;
  awayTeamId: number;
  /** Home win probability in [0, 1]. */
  home: number;
  final: boolean;
  homeAccent: string;
  awayAccent: string;
};

export function WinProbability({
  homeTeamId,
  awayTeamId,
  home,
  final,
  homeAccent,
  awayAccent,
}: WinProbabilityProps) {
  const homePct = Math.round(home * 100);
  const awayPct = 100 - homePct;
  const homeColor = homeAccent;
  const awayColor = awayAccent;

  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2.5">
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="text-muted">
          win probability <span className="text-faint">· baseline</span>
        </span>
        <span className="font-mono text-faint">
          {teamLabel(awayTeamId).abbr} {awayPct}% · {teamLabel(homeTeamId).abbr} {homePct}%
        </span>
      </div>
      <div
        className="flex h-2 overflow-hidden rounded-full"
        role="img"
        aria-label={`Win probability: home ${homePct}%, away ${awayPct}%`}
      >
        <div
          style={{
            width: `${awayPct}%`,
            background: awayColor,
            transition: "width 320ms ease-out",
          }}
        />
        <div
          style={{
            width: `${homePct}%`,
            background: homeColor,
            transition: "width 320ms ease-out",
          }}
        />
      </div>
      {final && (
        <div className="mt-1.5 text-[11px] text-faint">Game decided.</div>
      )}
    </div>
  );
}
