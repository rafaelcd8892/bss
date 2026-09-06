export type GameParams = {
  homeTeamId: number;
  awayTeamId: number;
  seed: number;
  innings: number;
};

export const DEFAULT_PARAMS: GameParams = {
  homeTeamId: 147,
  awayTeamId: 121,
  seed: 1234,
  innings: 9,
};

/**
 * The simulation is fully determined by (teams, seed, innings), so the URL is a
 * complete replay link — no server state required.
 */
export function readParams(): { params: GameParams; fromUrl: boolean } {
  const query = new URLSearchParams(window.location.search);
  const read = (key: string, fallback: number, minimum: number) => {
    const raw = query.get(key);
    if (raw === null) return fallback;
    const value = Number(raw);
    return Number.isFinite(value) && value >= minimum ? Math.floor(value) : fallback;
  };

  return {
    params: {
      homeTeamId: read("home", DEFAULT_PARAMS.homeTeamId, 1),
      awayTeamId: read("away", DEFAULT_PARAMS.awayTeamId, 1),
      seed: read("seed", DEFAULT_PARAMS.seed, 0),
      innings: read("innings", DEFAULT_PARAMS.innings, 9),
    },
    fromUrl: query.has("home") && query.has("away") && query.has("seed"),
  };
}

export function paramsToQuery(params: GameParams): string {
  const query = new URLSearchParams({
    home: String(params.homeTeamId),
    away: String(params.awayTeamId),
    seed: String(params.seed),
  });
  if (params.innings !== DEFAULT_PARAMS.innings) query.set("innings", String(params.innings));
  return query.toString();
}

export function syncUrl(params: GameParams): void {
  window.history.replaceState(null, "", `${window.location.pathname}?${paramsToQuery(params)}`);
}

export function shareUrl(params: GameParams): string {
  return `${window.location.origin}${window.location.pathname}?${paramsToQuery(params)}`;
}
