import { useState } from "react";
import { teamCapUrl } from "../media";
import { teamLabel } from "../teams";

/**
 * A club's cap logo, falling back to its colored initials.
 *
 * The image is third-party (ADR-025) and a broken or blocked request must not leave a
 * hole in the layout, so the fallback is a real label rather than an empty box.
 */
export function TeamLogo({
  teamId,
  dark,
  size = 20,
  className = "",
}: {
  teamId: number;
  dark: boolean;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const label = teamLabel(teamId);

  if (failed) {
    return (
      <span
        className={`inline-flex shrink-0 items-center justify-center rounded-sm text-[9px] font-medium ${className}`}
        style={{ width: size, height: size, background: label.primary, color: "#fff" }}
        aria-hidden
      >
        {label.abbr.slice(0, 3)}
      </span>
    );
  }

  return (
    <img
      src={teamCapUrl(teamId, dark)}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`shrink-0 object-contain ${className}`}
      style={{ width: size, height: size }}
    />
  );
}
