import type { Play } from "../api/client";

type PlayLogProps = {
  /** Plays up to the current index, oldest first. */
  plays: Play[];
};

type EventStyle = { label: string; bar: string; row?: string; label_ink?: string };

const EVENT_STYLE: Record<string, EventStyle> = {
  home_run: {
    label: "HR",
    bar: "var(--color-ev-hr)",
    row: "bg-ev-hr-bg text-ev-hr-ink",
    label_ink: "text-ev-hr",
  },
  triple: { label: "3B", bar: "var(--color-ev-hr)", label_ink: "text-ev-hr" },
  double: { label: "2B", bar: "var(--color-ev-xbh)", label_ink: "text-ev-xbh" },
  single: { label: "1B", bar: "var(--color-ev-hit)", label_ink: "text-ev-hit" },
  walk: { label: "BB", bar: "var(--color-ev-walk)", label_ink: "text-muted" },
  out: { label: "OUT", bar: "var(--color-ev-out)", label_ink: "text-faint" },
  tiebreaker: { label: "TB", bar: "var(--color-ev-xbh)", label_ink: "text-ev-xbh" },
};

type Entry =
  | { kind: "play"; play: Play; current: boolean }
  | { kind: "outs"; count: number; key: string };

/** Collapse runs of 3+ consecutive outs so hits stand out in the stream. */
function buildEntries(newestFirst: Play[]): Entry[] {
  const entries: Entry[] = [];
  let i = 0;
  while (i < newestFirst.length) {
    const play = newestFirst[i];
    if (play.event === "out") {
      let j = i;
      while (j < newestFirst.length && newestFirst[j].event === "out") j += 1;
      const count = j - i;
      // Never fold the newest play away: the viewer must always see what just happened.
      const foldable = count >= 3 && i > 0;
      if (foldable) {
        entries.push({ kind: "outs", count, key: `outs-${play.play_index}` });
        i = j;
        continue;
      }
    }
    entries.push({ kind: "play", play, current: i === 0 });
    i += 1;
  }
  return entries;
}

export function PlayLog({ plays }: PlayLogProps) {
  const newestFirst = [...plays].reverse();
  const entries = buildEntries(newestFirst).slice(0, 11);

  return (
    <div className="flex h-full flex-col gap-0.5 overflow-hidden rounded-md border border-line bg-surface p-1.5">
      {entries.length === 0 ? (
        <div className="px-2.5 py-3 text-sm text-faint">
          Press simulate to start the game.
        </div>
      ) : (
        entries.map((entry) =>
          entry.kind === "outs" ? (
            <div
              key={entry.key}
              className="flex items-center gap-2 border-l-[3px] px-2.5 py-1 text-xs text-faint"
              style={{ borderLeftColor: "var(--color-ev-out)" }}
            >
              <span className="w-9 shrink-0">···</span>
              <span>{entry.count} outs in a row</span>
            </div>
          ) : (
            <PlayRow key={entry.play.play_index} play={entry.play} current={entry.current} />
          ),
        )
      )}
    </div>
  );
}

function PlayRow({ play, current }: { play: Play; current: boolean }) {
  const style = EVENT_STYLE[play.event] ?? EVENT_STYLE.out;
  const runs = play.runs_scored_on_play;

  return (
    <div
      className={`flex items-baseline gap-2 border-l-[3px] px-2.5 py-1.5 ${style.row ?? ""} ${
        current ? "bss-slide-in" : ""
      } ${current && !style.row ? "bg-raised" : ""}`}
      style={{ borderLeftColor: style.bar }}
    >
      <span className={`w-9 shrink-0 text-xs font-medium ${style.label_ink ?? "text-faint"}`}>
        {style.label}
      </span>
      <span className={`text-[13px] leading-snug ${style.row ? "" : "text-ink"}`}>
        {play.batter_name && <span className="font-medium">{play.batter_name} — </span>}
        <span className={style.row ? "" : play.event === "out" ? "text-muted" : ""}>
          {play.description}
        </span>
      </span>
      {runs > 0 && (
        <span
          className="ml-auto shrink-0 rounded px-1.5 py-0.5 text-[11px] font-medium tabular-nums"
          style={{ background: "var(--color-ev-hr)", color: "#fff" }}
        >
          +{runs}
        </span>
      )}
    </div>
  );
}
