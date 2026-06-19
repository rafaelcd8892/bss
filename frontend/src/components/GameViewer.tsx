import { useEffect, useMemo, useRef, useState } from "react";
import { api, type PlayByPlayResult, type Play } from "../api/client";
import { Diamond } from "./Diamond";
import { LineScore } from "./LineScore";
import { PlayLog } from "./PlayLog";
import { Scoreboard } from "./Scoreboard";

type Form = { homeTeamId: number; awayTeamId: number; seed: number; innings: number };

const SPEEDS = [
  { label: "0.5×", ms: 1400 },
  { label: "1×", ms: 700 },
  { label: "2×", ms: 350 },
  { label: "4×", ms: 160 },
];

export function GameViewer() {
  const [form, setForm] = useState<Form>({
    homeTeamId: 147,
    awayTeamId: 121,
    seed: 1234,
    innings: 9,
  });
  const [result, setResult] = useState<PlayByPlayResult | null>(null);
  const [index, setIndex] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [speedMs, setSpeedMs] = useState(700);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const plays = result?.plays ?? [];
  const lastIndex = plays.length - 1;
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!playing) return;
    if (index >= lastIndex) {
      setPlaying(false);
      return;
    }
    timer.current = window.setTimeout(() => setIndex((i) => i + 1), speedMs);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [playing, index, lastIndex, speedMs]);

  async function simulate() {
    setLoading(true);
    setError(null);
    setPlaying(false);
    const { data, error: apiError } = await api.POST("/api/v1/simulate/game/play-by-play", {
      body: {
        home_team_id: form.homeTeamId,
        away_team_id: form.awayTeamId,
        innings: form.innings,
        context: { seed: form.seed, model_version: "baseline-v1", data_snapshot_id: "ui" },
      },
    });
    setLoading(false);
    if (apiError || !data) {
      setError("Simulation request failed. Is the API running on :8000?");
      return;
    }
    setResult(data.result);
    setIndex(-1);
    setPlaying(true);
  }

  const current: Play | null = index >= 0 ? plays[index] ?? null : null;
  const homeScore = current?.home_score_after_play ?? 0;
  const awayScore = current?.away_score_after_play ?? 0;
  const playsSoFar = index >= 0 ? plays.slice(0, index + 1) : [];
  const { lineHome, lineAway } = useMemo(() => partialLine(playsSoFar), [playsSoFar.length]);

  return (
    <div className="flex flex-col gap-3.5">
      <ControlsBar
        form={form}
        onChange={setForm}
        onSimulate={simulate}
        loading={loading}
        canPlay={plays.length > 0}
        playing={playing}
        onPlayPause={() => setPlaying((p) => !p)}
        onStep={() => setIndex((i) => Math.min(i + 1, lastIndex))}
        onReset={() => {
          setIndex(-1);
          setPlaying(false);
        }}
        speedMs={speedMs}
        onSpeed={setSpeedMs}
      />

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <Scoreboard
        homeTeamId={form.homeTeamId}
        awayTeamId={form.awayTeamId}
        homeScore={homeScore}
        awayScore={awayScore}
        inning={current?.inning ?? 1}
        half={current?.half ?? null}
        outs={current?.outs_after ?? 0}
      />

      <div className="grid grid-cols-[230px_minmax(0,1fr)] gap-2.5">
        <div className="rounded-md border border-neutral-200 bg-white p-2">
          <Diamond bases={current?.bases_after ?? "000"} />
          <div className="px-1.5 pb-1 pt-1 text-xs text-neutral-500">
            {current ? `play ${current.play_index} of ${plays.length}` : "ready"}
          </div>
        </div>
        <PlayLog plays={playsSoFar} />
      </div>

      <LineScore
        homeTeamId={form.homeTeamId}
        awayTeamId={form.awayTeamId}
        lineHome={lineHome}
        lineAway={lineAway}
        homeScore={homeScore}
        awayScore={awayScore}
      />

      {result && index >= lastIndex && (
        <div className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-600">
          Final · winner {labelFor(result, form)} · deterministic for seed {form.seed}.
        </div>
      )}
    </div>
  );
}

function labelFor(result: PlayByPlayResult, form: Form): string {
  return result.summary.winner_team_id === form.homeTeamId ? "home" : "away";
}

function partialLine(plays: Play[]): { lineHome: number[]; lineAway: number[] } {
  const lineHome: number[] = [];
  const lineAway: number[] = [];
  for (const play of plays) {
    if (play.event === "tiebreaker") continue;
    const i = play.inning - 1;
    const line = play.half === "bottom" ? lineHome : lineAway;
    while (line.length <= i) line.push(0);
    line[i] += play.runs_scored_on_play;
  }
  return { lineHome, lineAway };
}

const SPEED_BUTTON = "rounded-md border border-neutral-200 px-2 py-1 text-xs hover:bg-neutral-100";

type ControlsProps = {
  form: Form;
  onChange: (form: Form) => void;
  onSimulate: () => void;
  loading: boolean;
  canPlay: boolean;
  playing: boolean;
  onPlayPause: () => void;
  onStep: () => void;
  onReset: () => void;
  speedMs: number;
  onSpeed: (ms: number) => void;
};

function ControlsBar(props: ControlsProps) {
  const { form, onChange } = props;
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-md border border-neutral-200 bg-white px-3.5 py-3">
      <NumberField
        label="home"
        value={form.homeTeamId}
        onChange={(v) => onChange({ ...form, homeTeamId: v })}
      />
      <NumberField
        label="away"
        value={form.awayTeamId}
        onChange={(v) => onChange({ ...form, awayTeamId: v })}
      />
      <NumberField label="seed" value={form.seed} onChange={(v) => onChange({ ...form, seed: v })} />
      <button
        onClick={props.onSimulate}
        disabled={props.loading}
        className="rounded-md bg-neutral-900 px-3.5 py-2 text-sm text-white hover:bg-neutral-700 disabled:opacity-50"
      >
        {props.loading ? "simulating…" : "simulate"}
      </button>

      <div className="ml-auto flex items-center gap-1.5">
        <button onClick={props.onPlayPause} disabled={!props.canPlay} className={SPEED_BUTTON}>
          {props.playing ? "pause" : "play"}
        </button>
        <button onClick={props.onStep} disabled={!props.canPlay} className={SPEED_BUTTON}>
          step
        </button>
        <button onClick={props.onReset} disabled={!props.canPlay} className={SPEED_BUTTON}>
          reset
        </button>
        {SPEEDS.map((s) => (
          <button
            key={s.ms}
            onClick={() => props.onSpeed(s.ms)}
            className={`${SPEED_BUTTON} ${props.speedMs === s.ms ? "bg-neutral-900 text-white" : ""}`}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}

type NumberFieldProps = { label: string; value: number; onChange: (v: number) => void };

function NumberField({ label, value, onChange }: NumberFieldProps) {
  return (
    <label className="flex flex-col gap-1 text-xs text-neutral-500">
      {label}
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-24 rounded-md border border-neutral-200 px-2 py-1.5 text-sm text-neutral-900"
      />
    </label>
  );
}
