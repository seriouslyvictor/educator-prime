import { useEffect, useMemo, useState } from "react";
import type { ThemeMode } from "../types";

const themeKey = "classroom-downloader-theme";

function getInitialTheme(): ThemeMode {
  const stored = localStorage.getItem(themeKey);
  if (stored === "light" || stored === "dark" || stored === "system") {
    return stored;
  }
  return "system";
}

function resolveTheme(mode: ThemeMode): "light" | "dark" {
  if (mode !== "system") return mode;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function useThemePreference() {
  const [mode, setMode] = useState<ThemeMode>(getInitialTheme);
  const [systemTick, setSystemTick] = useState(0);
  const resolvedTheme = useMemo(() => resolveTheme(mode), [mode, systemTick]);

  useEffect(() => {
    localStorage.setItem(themeKey, mode);
    document.documentElement.dataset.theme = resolvedTheme;
    // Activate shadcn's @custom-variant dark (&:is(.dark *)) so shadcn screens
    // honour dark mode. The home-brewed system keys on [data-theme] only; no
    // *.module.css uses a .dark selector, so this toggle has no side-effect there.
    document.documentElement.classList.toggle("dark", resolvedTheme === "dark");
  }, [mode, resolvedTheme]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setSystemTick((tick) => tick + 1);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  return { mode, setMode, resolvedTheme };
}
