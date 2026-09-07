import { useEffect, useRef, useState } from "react";
import { TeamLogo } from "../../components/TeamLogo";
import { teamLabel } from "../../teams";

type ScoreboardProps = {
  homeTeamId: number;
  awayTeamId: number;
  homeScore: number;
  awayScore: number;
  inning: number;
  half: "top" | "bottom" | null;
  outs: number;
  homeAccent: string;
  awayAccent: string;
  dark: boolean;
};

export function Scoreboard({
  homeTeamId,
  awayTeamId,
  homeScore,
  awayScore,
  inning,
  half,
  outs,
  homeAccent,
  awayAccent,
  dark,
}: ScoreboardProps) {
  const home = teamLabel(homeTeamId);
  const away = teamLabel(awayTeamId);

  return (
    <div className="flex items-stretch gap-2.5">
      <TeamCard
        teamId={awayTeamId}
        dark={dark}
        name={away.name}
        abbr={away.abbr}
        accent={awayAccent}
        score={awayScore}
        batting={half === "top"}
        side="away"
        align="left"
      />
      <div className="min-w-[118px] rounded-md border border-line bg-surface px-4 py-2.5 text-center">
        <div className="flex items-center justify-center gap-1.5 text-sm text-muted">
          <span aria-hidden className="text-[10px]">
            {half === "bottom" ? "▼" : "▲"}
          </span>
          {half ? `${half === "top" ? "top" : "bot"} ${ordinal(inning)}` : "pregame"}
        </div>
        <div className="my-1.5 flex justify-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className={`h-2.5 w-2.5 rounded-full transition-colors ${
                i < outs ? "bg-ev-xbh" : "border border-line-strong"
              }`}
            />
          ))}
        </div>
        <div className="font-mono text-xs text-faint">{outs} out{outs === 1 ? "" : "s"}</div>
      </div>
      <TeamCard
        teamId={homeTeamId}
        dark={dark}
        name={home.name}
        abbr={home.abbr}
        accent={homeAccent}
        score={homeScore}
        batting={half === "bottom"}
        side="home"
        align="right"
      />
    </div>
  );
}

type TeamCardProps = {
  teamId: number;
  dark: boolean;
  name: string;
  abbr: string;
  accent: string;
  score: number;
  batting: boolean;
  side: string;
  align: "left" | "right";
};

function TeamCard({
  teamId,
  dark,
  name,
  abbr,
  accent,
  score,
  batting,
  side,
  align,
}: TeamCardProps) {
  const pop = useScorePop(score);
  const meta = (
    <div className={`min-w-0 flex-1 ${align === "right" ? "text-right" : "text-left"}`}>
      <div
        className={`flex items-center gap-1.5 ${align === "right" ? "justify-end" : ""}`}
      >
        {align === "left" && <TeamLogo teamId={teamId} dark={dark} size={22} />}
        <div className="truncate text-sm font-medium text-ink">{name}</div>
        {align === "right" && <TeamLogo teamId={teamId} dark={dark} size={22} />}
      </div>
      <div
        className={`flex items-center gap-1 text-xs text-faint ${
          align === "right" ? "justify-end" : ""
        }`}
      >
        {batting ? (
          <>
            <span
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{ background: accent }}
              aria-hidden
            />
            batting
          </>
        ) : (
          <>
            {abbr} · {side}
          </>
        )}
      </div>
    </div>
  );
  const value = (
    <div className={`text-3xl font-medium tabular-nums ${pop ? "bss-pop" : ""}`}>{score}</div>
  );

  return (
    <div
      className="flex flex-1 items-center justify-between gap-3 rounded-md border border-line bg-surface px-3.5 py-2.5"
      style={
        align === "left"
          ? { borderLeft: `4px solid ${accent}` }
          : { borderRight: `4px solid ${accent}` }
      }
    >
      {align === "left" ? (
        <>
          {meta}
          {value}
        </>
      ) : (
        <>
          {value}
          {meta}
        </>
      )}
    </div>
  );
}

/** Briefly flags a score change so the number can celebrate. */
function useScorePop(score: number): boolean {
  const previous = useRef(score);
  const [pop, setPop] = useState(false);

  useEffect(() => {
    if (score > previous.current) {
      setPop(true);
      const timer = window.setTimeout(() => setPop(false), 400);
      previous.current = score;
      return () => window.clearTimeout(timer);
    }
    previous.current = score;
  }, [score]);

  return pop;
}

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] ?? s[v] ?? s[0]);
}
