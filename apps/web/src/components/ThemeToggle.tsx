import type { ThemeMode } from "../types";
import { AppIcon } from "./icons";

export function ThemeToggle({
  mode,
  onChange,
}: {
  mode: ThemeMode;
  onChange: (mode: ThemeMode) => void;
}) {
  const nextMode: ThemeMode = mode === "system" ? "dark" : mode === "dark" ? "light" : "system";
  const label = mode === "system" ? "Sistema" : mode === "dark" ? "Escuro" : "Claro";
  return (
    <button className="icon-text-btn" onClick={() => onChange(nextMode)} title="Alternar tema">
      <AppIcon name={mode === "dark" ? "moon" : "sun"} />
      {label}
    </button>
  );
}
