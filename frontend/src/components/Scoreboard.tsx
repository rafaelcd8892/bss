import { teamLabel } from "../teams";

type ScoreboardProps = {
  homeTeamId: number;
  awayTeamId: number;
  homeScore: number;
  awayScore: number;
  inning: number;
  half: "top" | "bottom" | null;
  outs: number;
};

export function Scoreboard({
  homeTeamId,
  awayTeamId,
  homeScore,
  awayScore,
  inning,
  half,
  outs,
}: ScoreboardProps) {
  const home = teamLabel(homeTeamId);
  const away = teamLabel(awayTeamId);
  const halfLabel = half === "top" ? "top" : half === "bottom" ? "bottom" : "—";

  return (
    <div className="flex items-stretch gap-2.5">
      <TeamCard name={away.name} sub="away" score={awayScore} align="left" />
      <div className="min-w-[124px] rounded-md border border-neutral-200 bg-white px-4 py-2.5 text-center">
        <div className="flex items-center justify-center gap-1 text-sm text-neutral-500">
          <span aria-hidden>{half === "bottom" ? "▼" : "▲"}</span>
          {halfLabel} {inning > 0 ? ordinal(inning) : ""}
        </div>
        <div className="my-1.5 flex justify-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className={`h-2.5 w-2.5 rounded-full ${
                i < outs ? "bg-amber-500" : "border border-neutral-300"
              }`}
            />
          ))}
        </div>
        <div className="font-mono text-xs text-neutral-500">{outs} outs</div>
      </div>
      <TeamCard name={home.name} sub="home" score={homeScore} align="right" />
    </div>
  );
}

type TeamCardProps = {
  name: string;
  sub: string;
  score: number;
  align: "left" | "right";
};

function TeamCard({ name, sub, score, align }: TeamCardProps) {
  const meta = (
    <div className={align === "right" ? "text-right" : "text-left"}>
      <div className="text-sm text-neutral-600">{name}</div>
      <div className="text-xs text-neutral-400">{sub}</div>
    </div>
  );
  return (
    <div className="flex flex-1 items-center justify-between rounded-md border border-neutral-200 bg-white px-3.5 py-2.5">
      {align === "left" ? meta : <div className="text-3xl font-medium">{score}</div>}
      {align === "left" ? <div className="text-3xl font-medium">{score}</div> : meta}
    </div>
  );
}

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] ?? s[v] ?? s[0]);
}
