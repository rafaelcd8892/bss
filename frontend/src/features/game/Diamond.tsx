import { useEffect, useRef, useState } from "react";

type DiamondProps = {
  /** 3 chars: on_first, on_second, on_third (e.g. "101"). */
  bases: string;
  /** Batting team accent, used to color occupied bases. */
  accent: string;
};

const HOME = { x: 110, y: 164 };

export function Diamond({ bases, accent }: DiamondProps) {
  const occupied = [bases[0] === "1", bases[1] === "1", bases[2] === "1"];
  const previous = useRef(occupied);
  const [justReached, setJustReached] = useState([false, false, false]);

  useEffect(() => {
    const reached = occupied.map((on, i) => on && !previous.current[i]);
    previous.current = occupied;
    if (reached.some(Boolean)) {
      setJustReached(reached);
      const timer = window.setTimeout(() => setJustReached([false, false, false]), 400);
      return () => window.clearTimeout(timer);
    }
    setJustReached([false, false, false]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bases]);

  return (
    <svg viewBox="0 0 220 190" className="mx-auto block w-full max-w-[230px]" role="img" aria-label={`Bases: ${bases}`}>
      <path
        d={`M${HOME.x},${HOME.y} L20,74 A 127,127 0 0 1 200,74 Z`}
        fill="var(--color-grass)"
      />
      <polygon points="110,174 172,108 110,46 48,108" fill="var(--color-dirt)" />
      <polygon points="110,150 148,108 110,66 72,108" fill="var(--color-grass-alt)" />
      <polygon
        points="110,160 162,108 110,56 58,108"
        fill="none"
        stroke="var(--color-chalk)"
        strokeWidth={1.5}
        opacity={0.85}
      />
      <path
        d={`M${HOME.x},${HOME.y} L24,78 M${HOME.x},${HOME.y} L196,78`}
        stroke="var(--color-chalk)"
        strokeWidth={1.2}
        opacity={0.6}
      />
      <circle cx={110} cy={108} r={11} fill="var(--color-dirt)" />
      <rect x={107} y={104} width={6} height={3} rx={1} fill="var(--color-chalk)" opacity={0.8} />

      <Base x={162} y={108} occupied={occupied[0]} pop={justReached[0]} accent={accent} label="1B" />
      <Base x={110} y={56} occupied={occupied[1]} pop={justReached[1]} accent={accent} label="2B" />
      <Base x={58} y={108} occupied={occupied[2]} pop={justReached[2]} accent={accent} label="3B" />

      <polygon
        points="110,158 116,163 113,170 107,170 104,163"
        fill="var(--color-chalk)"
        stroke="var(--color-line-strong)"
        strokeWidth={0.75}
      />
    </svg>
  );
}

type BaseProps = {
  x: number;
  y: number;
  occupied: boolean;
  pop: boolean;
  accent: string;
  label: string;
};

function Base({ x, y, occupied, pop, accent, label }: BaseProps) {
  return (
    <g className={pop ? "bss-pop" : undefined} style={{ transformOrigin: `${x}px ${y}px` }}>
      <rect
        x={x - 8}
        y={y - 8}
        width={16}
        height={16}
        rx={2}
        transform={`rotate(45 ${x} ${y})`}
        fill={occupied ? accent : "var(--color-chalk)"}
        stroke={occupied ? accent : "var(--color-line-strong)"}
        strokeWidth={1.5}
        style={{ transition: "fill 220ms ease-out, stroke 220ms ease-out" }}
      />
      <title>{`${label}${occupied ? " — occupied" : ""}`}</title>
    </g>
  );
}
