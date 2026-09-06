import { useMemo, useRef, useState } from "react";
import type { Play } from "../../api/client";

type ScrubberProps = {
  plays: Play[];
  index: number;
  onScrub: (index: number) => void;
};

/** Visual weight per event: the big moments should be findable at a glance. */
const TICK: Record<string, { color: string; height: number }> = {
  home_run: { color: "var(--color-ev-hr)", height: 100 },
  triple: { color: "var(--color-ev-hr)", height: 80 },
  double: { color: "var(--color-ev-xbh)", height: 66 },
  single: { color: "var(--color-ev-hit)", height: 52 },
  walk: { color: "var(--color-ev-walk)", height: 38 },
  out: { color: "var(--color-ev-out)", height: 26 },
  tiebreaker: { color: "var(--color-ev-xbh)", height: 100 },
};

export function Scrubber({ plays, index, onScrub }: ScrubberProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);

  const innings = useMemo(() => inningSpans(plays), [plays]);

  if (plays.length === 0) return null;

  function positionFrom(clientX: number) {
    const track = trackRef.current;
    if (!track) return;
    const rect = track.getBoundingClientRect();
    const ratio = (clientX - rect.left) / rect.width;
    const next = Math.round(ratio * (plays.length - 1));
    onScrub(Math.min(Math.max(next, 0), plays.length - 1));
  }

  const progress = index < 0 ? 0 : (index + 1) / plays.length;

  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2.5">
      <div className="mb-1.5 flex items-center justify-between text-xs text-muted">
        <span>drag to scrub any moment</span>
        <span className="font-mono text-faint">
          play {Math.max(index + 1, 0)} / {plays.length}
        </span>
      </div>

      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-label="Game timeline"
        aria-valuemin={0}
        aria-valuemax={plays.length}
        aria-valuenow={index + 1}
        className="relative h-7 cursor-pointer touch-none select-none"
        onPointerDown={(e) => {
          setDragging(true);
          e.currentTarget.setPointerCapture(e.pointerId);
          positionFrom(e.clientX);
        }}
        onPointerMove={(e) => dragging && positionFrom(e.clientX)}
        onPointerUp={(e) => {
          setDragging(false);
          e.currentTarget.releasePointerCapture(e.pointerId);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") onScrub(Math.max(index - 1, 0));
          if (e.key === "ArrowRight") onScrub(Math.min(index + 1, plays.length - 1));
        }}
      >
        <div className="pointer-events-none absolute inset-0 flex items-end gap-px">
          {plays.map((play, i) => {
            const tick = TICK[play.event] ?? TICK.out;
            return (
              <div
                key={play.play_index}
                className="flex-1 rounded-[1px]"
                style={{
                  height: `${tick.height}%`,
                  background: tick.color,
                  opacity: i <= index ? 1 : 0.4,
                }}
              />
            );
          })}
        </div>

        {innings.map((span) => (
          <div
            key={span.inning}
            className="pointer-events-none absolute bottom-0 top-0 w-px"
            style={{ left: `${span.start * 100}%`, background: "var(--color-line)" }}
          />
        ))}

        <div
          className="pointer-events-none absolute bottom-0 top-0 w-0.5 rounded"
          style={{ left: `calc(${progress * 100}% - 1px)`, background: "var(--color-ink)" }}
        />
      </div>

      <div className="relative mt-1 h-3">
        {innings.map((span) => (
          <span
            key={span.inning}
            className="absolute font-mono text-[10px] text-faint"
            style={{ left: `${((span.start + span.end) / 2) * 100}%`, transform: "translateX(-50%)" }}
          >
            {span.inning}
          </span>
        ))}
      </div>
    </div>
  );
}

type InningSpan = { inning: number; start: number; end: number };

function inningSpans(plays: Play[]): InningSpan[] {
  if (plays.length === 0) return [];
  const spans: InningSpan[] = [];
  let startIndex = 0;
  for (let i = 1; i <= plays.length; i += 1) {
    const changed = i === plays.length || plays[i].inning !== plays[startIndex].inning;
    if (changed) {
      spans.push({
        inning: plays[startIndex].inning,
        start: startIndex / plays.length,
        end: i / plays.length,
      });
      startIndex = i;
    }
  }
  return spans;
}
