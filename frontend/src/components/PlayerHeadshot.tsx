import { useState } from "react";
import { playerHeadshotUrl } from "../media";

/**
 * A player's headshot, falling back to their initials.
 *
 * Every player has an id but not every player has a photo, and the service answers a
 * miss with a generic silhouette rather than a 404 — so the fallback here is for the
 * request failing outright, not for the player being unknown.
 */
export function PlayerHeadshot({
  playerId,
  name,
  size = 40,
  accent,
}: {
  playerId: number;
  name: string;
  size?: 60 | 120 | 240 | number;
  accent?: string;
}) {
  const [failed, setFailed] = useState(false);
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");

  const box = { width: size, height: size };

  if (failed) {
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center rounded-full text-[11px] font-medium text-app"
        style={{ ...box, background: accent ?? "var(--color-line-strong)" }}
        aria-hidden
      >
        {initials}
      </span>
    );
  }

  return (
    <img
      src={playerHeadshotUrl(playerId, 120)}
      alt={name}
      loading="lazy"
      onError={() => setFailed(true)}
      className="shrink-0 rounded-full bg-raised object-cover"
      style={box}
    />
  );
}
