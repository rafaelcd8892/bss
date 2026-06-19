type TeamLabel = { abbr: string; name: string };

const KNOWN_TEAMS: Record<number, TeamLabel> = {
  147: { abbr: "NYY", name: "New York Yankees" },
  121: { abbr: "NYM", name: "New York Mets" },
  119: { abbr: "LAD", name: "Los Angeles Dodgers" },
  111: { abbr: "BOS", name: "Boston Red Sox" },
  158: { abbr: "MIL", name: "Milwaukee Brewers" },
  137: { abbr: "SF", name: "San Francisco Giants" },
  112: { abbr: "CHC", name: "Chicago Cubs" },
  117: { abbr: "HOU", name: "Houston Astros" },
};

export function teamLabel(teamId: number): TeamLabel {
  return KNOWN_TEAMS[teamId] ?? { abbr: `#${teamId}`, name: `Team ${teamId}` };
}
