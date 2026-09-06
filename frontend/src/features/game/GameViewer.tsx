import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type Play, type PlayByPlayResult } from "../../api/client";
import { matchupAccents, teamLabel } from "../../teams";
import { useTeamCatalog } from "../../useTeamCatalog";
import { readParams, shareUrl, syncUrl, type GameParams } from "./url";
import { BoxScore } from "./BoxScore";
import { Diamond } from "./Diamond";
import { LineScore } from "./LineScore";
import { PlayLog } from "./PlayLog";
import { Scoreboard } from "./Scoreboard";
import { Scrubber } from "./Scrubber";
import { TeamPicker } from "./TeamPicker";
import { WinProbability } from "./WinProbability";

const SPEEDS = [
  { label: "0.5×", ms: 1400 },
  { label: "1×", ms: 700 },
  { label: "2×", ms: 350 },
  { label: "4×", ms: 160 },
];

const BUTTON =
  "rounded-md border border-line bg-surface px-2 py-1 text-xs text-muted transition-colors hover:text-ink disabled:cursor-not-allowed disabled:opacity-40";

export function GameViewer({ dark }: { dark: boolean }) {
  const initial = useRef(readParams());
  const [form, setForm] = useState<GameParams>(initial.current.params);
  const [result, setResult] = useState<PlayByPlayResult | null>(null);
  const [index, setIndex] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [speedMs, setSpeedMs] = useState(700);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const teams = useTeamCatalog();
  const plays = useMemo(() => result?.plays ?? [], [result]);
  const lastIndex = plays.length - 1;
  const timer = useRef<number | null>(null);

  const simulate = useCallback(async (params: GameParams) => {
    setLoading(true);
    setError(null);
    setPlaying(false);
    const { data, error: apiError } = await api.POST("/api/v1/simulate/game/play-by-play", {
      body: {
        home_team_id: params.homeTeamId,
        away_team_id: params.awayTeamId,
        innings: params.innings,
        context: { seed: params.seed, model_version: "baseline-v1", data_snapshot_id: "ui" },
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
    syncUrl(params);
  }, []);

  // A URL that already carries a matchup is a replay link: play it straight away.
  useEffect(() => {
    if (initial.current.fromUrl) void simulate(initial.current.params);
  }, [simulate]);

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

  const step = useCallback(() => {
    setPlaying(false);
    setIndex((i) => Math.min(i + 1, lastIndex));
  }, [lastIndex]);

  const stepBack = useCallback(() => {
    setPlaying(false);
    setIndex((i) => Math.max(i - 1, -1));
  }, []);

  const reset = useCallback(() => {
    setPlaying(false);
    setIndex(-1);
  }, []);

  // Keyboard transport controls, skipped while typing in a field.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
      if (plays.length === 0) return;

      if (event.key === " ") {
        event.preventDefault();
        setPlaying((p) => !p);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        step();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        stepBack();
      } else if (event.key.toLowerCase() === "r") {
        reset();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [plays.length, step, stepBack, reset]);

  const current: Play | null = index >= 0 ? plays[index] ?? null : null;
  const homeScore = current?.home_score_after_play ?? 0;
  const awayScore = current?.away_score_after_play ?? 0;
  const playsSoFar = useMemo(() => (index >= 0 ? plays.slice(0, index + 1) : []), [plays, index]);
  const { lineHome, lineAway } = useMemo(() => partialLine(playsSoFar), [playsSoFar]);
  // The win probability now travels with each play, computed by the same server-side
  // model that backs /predict/game — the client no longer keeps its own copy.
  const homeWinProbability = current?.home_win_probability ?? 0.5;
  const accents = useMemo(
    () => matchupAccents(form.homeTeamId, form.awayTeamId, dark),
    [form.homeTeamId, form.awayTeamId, dark],
  );
  const battingAccent = current
    ? current.batting_team_id === form.homeTeamId
      ? accents.home
      : accents.away
    : accents.away;
  const finished = plays.length > 0 && index >= lastIndex;

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(shareUrl(form));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setError("Could not copy the link. The URL bar already has it.");
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3 rounded-md border border-line bg-surface px-3.5 py-3">
        <div className="w-44">
          <TeamPicker
            label="away"
            value={form.awayTeamId}
            teams={teams}
            dark={dark}
            onChange={(awayTeamId) => setForm({ ...form, awayTeamId })}
          />
        </div>
        <div className="w-44">
          <TeamPicker
            label="home"
            value={form.homeTeamId}
            teams={teams}
            dark={dark}
            onChange={(homeTeamId) => setForm({ ...form, homeTeamId })}
          />
        </div>
        <label className="flex flex-col gap-1 text-xs text-muted">
          seed
          <div className="flex items-center gap-1">
            <input
              type="number"
              value={form.seed}
              onChange={(e) => setForm({ ...form, seed: Number(e.target.value) })}
              className="w-24 rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink outline-none"
            />
            <button
              onClick={() => setForm({ ...form, seed: Math.floor(Math.random() * 100000) })}
              className={BUTTON}
              title="Random seed"
            >
              ⟳
            </button>
          </div>
        </label>
        <button
          onClick={() => void simulate(form)}
          disabled={loading}
          className="rounded-md bg-ink px-3.5 py-2 text-sm text-app transition-opacity hover:opacity-85 disabled:opacity-50"
        >
          {loading ? "simulating…" : "simulate"}
        </button>

        <div className="ml-auto flex items-center gap-1.5">
          <button onClick={() => setPlaying((p) => !p)} disabled={!plays.length} className={BUTTON}>
            {playing ? "pause" : "play"}
          </button>
          <button onClick={stepBack} disabled={!plays.length} className={BUTTON} title="Left arrow">
            ‹
          </button>
          <button onClick={step} disabled={!plays.length} className={BUTTON} title="Right arrow">
            ›
          </button>
          <button onClick={reset} disabled={!plays.length} className={BUTTON}>
            reset
          </button>
          {SPEEDS.map((speed) => (
            <button
              key={speed.ms}
              onClick={() => setSpeedMs(speed.ms)}
              className={`${BUTTON} ${
                speedMs === speed.ms ? "border-ink bg-ink text-app hover:text-app" : ""
              }`}
            >
              {speed.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div
          className="rounded-md border px-3 py-2 text-sm"
          style={{
            borderColor: "var(--color-ev-hr)",
            background: "var(--color-ev-hr-bg)",
            color: "var(--color-ev-hr-ink)",
          }}
        >
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
        homeAccent={accents.home}
        awayAccent={accents.away}
      />

      {plays.length > 0 && (
        <WinProbability
          homeTeamId={form.homeTeamId}
          awayTeamId={form.awayTeamId}
          home={homeWinProbability}
          final={finished}
          homeAccent={accents.home}
          awayAccent={accents.away}
        />
      )}

      <div className="grid grid-cols-[236px_minmax(0,1fr)] gap-2.5 max-[720px]:grid-cols-1">
        <div className="flex flex-col rounded-md border border-line bg-surface p-2">
          <Diamond
            bases={current?.bases_after ?? "000"}
            accent={battingAccent}
          />
          <div className="mt-1 border-t border-line px-1.5 pt-2">
            <div className="text-[11px] text-faint">at bat</div>
            <div className="truncate text-[13px] font-medium text-ink">
              {current?.batter_name ?? "—"}
            </div>
            <div className="mt-1.5 line-clamp-2 text-xs text-muted">
              {current?.description ?? "Press simulate to start the game."}
            </div>
          </div>
        </div>
        <PlayLog plays={playsSoFar} />
      </div>

      <Scrubber
        plays={plays}
        index={index}
        onScrub={(next) => {
          setPlaying(false);
          setIndex(next);
        }}
      />

      <LineScore
        homeTeamId={form.homeTeamId}
        awayTeamId={form.awayTeamId}
        lineHome={lineHome}
        lineAway={lineAway}
        homeScore={homeScore}
        awayScore={awayScore}
        currentInning={current?.inning ?? null}
        homeAccent={accents.home}
        awayAccent={accents.away}
      />

      {finished && result && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-raised px-3.5 py-2.5 text-sm">
            <span className="text-ink">
              <span className="font-medium">Final</span>
              <span className="text-muted"> · </span>
              {teamLabel(result.summary.winner_team_id).name} win
              <span className="text-muted"> · reproducible from seed {form.seed}</span>
            </span>
            <button onClick={() => void copyLink()} className={BUTTON}>
              {copied ? "link copied" : "copy replay link"}
            </button>
          </div>
          <BoxScore
            plays={plays}
            homeTeamId={form.homeTeamId}
            awayTeamId={form.awayTeamId}
            homeAccent={accents.home}
            awayAccent={accents.away}
          />
        </>
      )}

      <p className="px-1 text-[11px] text-faint">
        space play/pause · ← → step · r reset · drag the timeline to scrub
      </p>
    </div>
  );
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
