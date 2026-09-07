/**
 * Club logos and player headshots, referenced by URL.
 *
 * MLBAM's terms permit individual, non-commercial, non-bulk use of their materials
 * (ADR-025), so these are linked rather than copied into our own storage: nothing is
 * downloaded, cached or redistributed, and the browser fetches them the same way it
 * would on any page that links an image.
 *
 * No database column is needed either — every URL is derivable from an id we already
 * hold.
 */

const TEAM_LOGO = "https://www.mlbstatic.com/team-logos";
const HEADSHOT = "https://midfield.mlbstatic.com/v1/people";

/** A club's primary logo, as SVG. */
export function teamLogoUrl(teamId: number): string {
  return `${TEAM_LOGO}/${teamId}.svg`;
}

/** A club's cap logo, which reads better at small sizes than the full mark. */
export function teamCapUrl(teamId: number, dark: boolean): string {
  const variant = dark ? "team-cap-on-dark" : "team-cap-on-light";
  return `${TEAM_LOGO}/${variant}/${teamId}.svg`;
}

/**
 * A player's headshot at the requested width.
 *
 * The service only renders a handful of sizes; asking for an arbitrary one returns a
 * blurred upscale, so the choice is deliberately narrow.
 */
export function playerHeadshotUrl(playerId: number, size: 60 | 120 | 240 = 120): string {
  return `${HEADSHOT}/${playerId}/spots/${size}`;
}
