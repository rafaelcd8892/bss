import type { Play } from "../api/client";

type PlayLogProps = {
  plays: Play[]; // already sliced up to the current index, newest last
};

const EVENT_STYLE: Record<string, { label: string; color: string }> = {
  home_run: { label: "HR", color: "border-l-orange-500 bg-orange-50 text-orange-900" },
  triple: { label: "3B", color: "border-l-orange-400 bg-orange-50/60 text-orange-900" },
  double: { label: "2B", color: "border-l-amber-400 text-neutral-900" },
  single: { label: "1B", color: "border-l-emerald-500 text-neutral-900" },
  walk: { label: "BB", color: "border-l-neutral-300 text-neutral-900" },
  out: { label: "OUT", color: "border-l-neutral-200 text-neutral-500" },
  tiebreaker: { label: "TB", color: "border-l-purple-400 text-purple-900" },
};

export function PlayLog({ plays }: PlayLogProps) {
  const recent = [...plays].reverse().slice(0, 12);

  return (
    <div className="flex h-full flex-col gap-0.5 rounded-md border border-neutral-200 bg-white p-1.5">
      {recent.length === 0 ? (
        <div className="px-2.5 py-3 text-sm text-neutral-400">Press play to start the game.</div>
      ) : (
        recent.map((play) => {
          const style = EVENT_STYLE[play.event] ?? EVENT_STYLE.out;
          return (
            <div
              key={play.play_index}
              className={`flex gap-2 border-l-[3px] px-2.5 py-1.5 ${style.color}`}
            >
              <span className="w-9 shrink-0 text-xs font-medium">{style.label}</span>
              <span className="text-[13px] leading-snug">
                {play.batter_name && <span className="font-medium">{play.batter_name} — </span>}
                {play.description}
              </span>
            </div>
          );
        })
      )}
    </div>
  );
}
