type DiamondProps = {
  bases: string; // 3 chars: on_first, on_second, on_third (e.g. "101")
};

const OCCUPIED = "#1d9e75";
const EMPTY = "#ffffff";
const STROKE = "#c9c9c2";

export function Diamond({ bases }: DiamondProps) {
  const onFirst = bases[0] === "1";
  const onSecond = bases[1] === "1";
  const onThird = bases[2] === "1";

  return (
    <svg viewBox="0 0 230 200" className="w-full" role="img" aria-label="Infield diamond">
      <polygon points="115,175 180,110 115,45 50,110" fill="none" stroke={STROKE} strokeWidth={1.5} />
      <circle cx={115} cy={110} r={13} fill="none" stroke="#e3e3de" strokeWidth={1} />
      <circle cx={115} cy={110} r={2.5} fill="#9a9a90" />
      <Base x={180} y={110} occupied={onFirst} label="1B" labelX={198} labelY={114} />
      <Base x={115} y={45} occupied={onSecond} label="2B" labelX={107} labelY={28} />
      <Base x={50} y={110} occupied={onThird} label="3B" labelX={22} labelY={114} />
      <rect
        x={106}
        y={166}
        width={18}
        height={18}
        rx={3}
        transform="rotate(45 115 175)"
        fill="#f0f0ec"
        stroke={STROKE}
      />
    </svg>
  );
}

type BaseProps = {
  x: number;
  y: number;
  occupied: boolean;
  label: string;
  labelX: number;
  labelY: number;
};

function Base({ x, y, occupied, label, labelX, labelY }: BaseProps) {
  return (
    <g>
      <rect
        x={x - 10}
        y={y - 10}
        width={20}
        height={20}
        rx={3}
        transform={`rotate(45 ${x} ${y})`}
        fill={occupied ? OCCUPIED : EMPTY}
        stroke={occupied ? OCCUPIED : STROKE}
        strokeWidth={1.5}
      />
      <text x={labelX} y={labelY} fontSize={11} fill="#9a9a90" textAnchor="middle">
        {label}
      </text>
    </g>
  );
}
