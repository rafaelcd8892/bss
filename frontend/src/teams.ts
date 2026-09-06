export type TeamLabel = {
  abbr: string;
  name: string;
  /** Official primary color. */
  primary: string;
  /** Official secondary color, used when the primary lacks contrast on a surface. */
  secondary: string;
};

/** MLB team ids as used by the MLB Stats API, with official club colors. */
const KNOWN_TEAMS: Record<number, TeamLabel> = {
  108: { abbr: "LAA", name: "Los Angeles Angels", primary: "#BA0021", secondary: "#C4CED4" },
  109: { abbr: "ARI", name: "Arizona Diamondbacks", primary: "#A71930", secondary: "#E3D4AD" },
  110: { abbr: "BAL", name: "Baltimore Orioles", primary: "#DF4601", secondary: "#FDB827" },
  111: { abbr: "BOS", name: "Boston Red Sox", primary: "#BD3039", secondary: "#C4CED4" },
  112: { abbr: "CHC", name: "Chicago Cubs", primary: "#0E3386", secondary: "#CC3433" },
  113: { abbr: "CIN", name: "Cincinnati Reds", primary: "#C6011F", secondary: "#C4CED4" },
  114: { abbr: "CLE", name: "Cleveland Guardians", primary: "#00385D", secondary: "#E50022" },
  115: { abbr: "COL", name: "Colorado Rockies", primary: "#33006F", secondary: "#C4CED4" },
  116: { abbr: "DET", name: "Detroit Tigers", primary: "#0C2340", secondary: "#FA4616" },
  117: { abbr: "HOU", name: "Houston Astros", primary: "#EB6E1F", secondary: "#002D62" },
  118: { abbr: "KC", name: "Kansas City Royals", primary: "#004687", secondary: "#BD9B60" },
  119: { abbr: "LAD", name: "Los Angeles Dodgers", primary: "#005A9C", secondary: "#EF3E42" },
  120: { abbr: "WSH", name: "Washington Nationals", primary: "#AB0003", secondary: "#14225A" },
  121: { abbr: "NYM", name: "New York Mets", primary: "#002D72", secondary: "#FF5910" },
  133: { abbr: "ATH", name: "Athletics", primary: "#003831", secondary: "#EFB21E" },
  134: { abbr: "PIT", name: "Pittsburgh Pirates", primary: "#27251F", secondary: "#FDB827" },
  135: { abbr: "SD", name: "San Diego Padres", primary: "#2F241D", secondary: "#FFC425" },
  136: { abbr: "SEA", name: "Seattle Mariners", primary: "#0C2C56", secondary: "#005C5C" },
  137: { abbr: "SF", name: "San Francisco Giants", primary: "#FD5A1E", secondary: "#27251F" },
  138: { abbr: "STL", name: "St. Louis Cardinals", primary: "#C41E3A", secondary: "#FEDB00" },
  139: { abbr: "TB", name: "Tampa Bay Rays", primary: "#092C5C", secondary: "#8FBCE6" },
  140: { abbr: "TEX", name: "Texas Rangers", primary: "#003278", secondary: "#C0111F" },
  141: { abbr: "TOR", name: "Toronto Blue Jays", primary: "#134A8E", secondary: "#1D2D5C" },
  142: { abbr: "MIN", name: "Minnesota Twins", primary: "#002B5C", secondary: "#D31145" },
  143: { abbr: "PHI", name: "Philadelphia Phillies", primary: "#E81828", secondary: "#002D72" },
  144: { abbr: "ATL", name: "Atlanta Braves", primary: "#CE1141", secondary: "#13274F" },
  145: { abbr: "CWS", name: "Chicago White Sox", primary: "#27251F", secondary: "#C4CED4" },
  146: { abbr: "MIA", name: "Miami Marlins", primary: "#00A3E0", secondary: "#EF3340" },
  147: { abbr: "NYY", name: "New York Yankees", primary: "#0C2340", secondary: "#8996A0" },
  158: { abbr: "MIL", name: "Milwaukee Brewers", primary: "#12284B", secondary: "#FFC52F" },
};

const FALLBACK: Omit<TeamLabel, "abbr" | "name"> = { primary: "#5f6b7a", secondary: "#95a1b0" };

export function teamLabel(teamId: number): TeamLabel {
  return (
    KNOWN_TEAMS[teamId] ?? { abbr: `#${teamId}`, name: `Team ${teamId}`, ...FALLBACK }
  );
}

export function allTeams(): Array<TeamLabel & { id: number }> {
  return Object.entries(KNOWN_TEAMS)
    .map(([id, team]) => ({ id: Number(id), ...team }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/** WCAG relative luminance, 0 (black) to 1 (white). */
function luminance(hex: string): number {
  const value = hex.replace("#", "");
  const toLinear = (channel: number) => {
    const c = channel / 255;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  const r = toLinear(parseInt(value.slice(0, 2), 16));
  const g = toLinear(parseInt(value.slice(2, 4), 16));
  const b = toLinear(parseInt(value.slice(4, 6), 16));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Pick the club color that stays visible against the current surface: several clubs
 * use a near-black navy that vanishes on a dark background, so fall back to the
 * secondary when the primary is too close to the surface.
 */
export function teamAccent(teamId: number, dark: boolean): string {
  const { primary, secondary } = teamLabel(teamId);
  const primaryLum = luminance(primary);
  if (dark && primaryLum < 0.09) {
    return luminance(secondary) > primaryLum ? secondary : "#8996A0";
  }
  if (!dark && primaryLum > 0.62) {
    return luminance(secondary) < primaryLum ? secondary : "#5f6b7a";
  }
  return primary;
}

function channels(hex: string): [number, number, number] {
  const value = hex.replace("#", "");
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ];
}

/** Weighted RGB distance ("redmean"), a cheap stand-in for perceptual difference. */
function colorDistance(a: string, b: string): number {
  const [r1, g1, b1] = channels(a);
  const [r2, g2, b2] = channels(b);
  const meanRed = (r1 + r2) / 2;
  const dr = r1 - r2;
  const dg = g1 - g2;
  const db = b1 - b2;
  return Math.sqrt(
    (2 + meanRed / 256) * dr * dr + 4 * dg * dg + (2 + (255 - meanRed) / 256) * db * db,
  );
}

/** Below this the two clubs read as the same color on a bar or a badge. */
const MIN_MATCHUP_DISTANCE = 120;
const NEUTRAL_ACCENT = "#8d8d84";

function alternateAccent(teamId: number, dark: boolean): string {
  const { primary, secondary } = teamLabel(teamId);
  const chosen = teamAccent(teamId, dark);
  const other = chosen === primary ? secondary : primary;
  const lum = luminance(other);
  if (dark && lum < 0.09) return NEUTRAL_ACCENT;
  if (!dark && lum > 0.62) return "#5f6b7a";
  return other;
}

/**
 * Distinct accents for any two clubs shown together. Many clubs share a near-identical
 * navy or red, which would make a scoreboard, win-probability bar or comparison
 * unreadable, so fall back to a club's secondary (and finally a neutral) until the two
 * colors are clearly distinct.
 */
export function pairAccents(
  firstTeamId: number,
  secondTeamId: number,
  dark: boolean,
): { first: string; second: string } {
  const first = teamAccent(firstTeamId, dark);
  const second = teamAccent(secondTeamId, dark);
  if (colorDistance(first, second) >= MIN_MATCHUP_DISTANCE) return { first, second };

  const secondAlt = alternateAccent(secondTeamId, dark);
  if (colorDistance(first, secondAlt) >= MIN_MATCHUP_DISTANCE) {
    return { first, second: secondAlt };
  }

  const firstAlt = alternateAccent(firstTeamId, dark);
  if (colorDistance(firstAlt, second) >= MIN_MATCHUP_DISTANCE) {
    return { first: firstAlt, second };
  }

  return { first, second: NEUTRAL_ACCENT };
}

/** Home/away naming for the game viewer. */
export function matchupAccents(
  homeTeamId: number,
  awayTeamId: number,
  dark: boolean,
): { home: string; away: string } {
  const { first, second } = pairAccents(homeTeamId, awayTeamId, dark);
  return { home: first, away: second };
}
