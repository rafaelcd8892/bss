import { useCallback, useEffect, useState } from "react";
import { currentTheme, persistTheme, storedTheme, systemTheme, type Theme } from "./theme";

export function useTheme(): { theme: Theme; dark: boolean; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(() => currentTheme());
  const [explicit, setExplicit] = useState<boolean>(() => storedTheme() !== null);

  // Side effects live here, not inside the state updater: React may invoke updaters
  // more than once, which would make persistence unreliable.
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    if (explicit) persistTheme(theme);
  }, [theme, explicit]);

  // Follow the OS until the user makes an explicit choice.
  useEffect(() => {
    if (explicit) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setTheme(systemTheme());
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [explicit]);

  const toggle = useCallback(() => {
    setExplicit(true);
    setTheme((previous) => (previous === "dark" ? "light" : "dark"));
  }, []);

  return { theme, dark: theme === "dark", toggle };
}
