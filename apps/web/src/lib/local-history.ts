import { useEffect, useState } from "react";
import type { LocalExportHistoryItem } from "../types";

const historyKey = "classroom-downloader-export-history";

function readHistory(): LocalExportHistoryItem[] {
  try {
    const stored = localStorage.getItem(historyKey);
    return stored ? (JSON.parse(stored) as LocalExportHistoryItem[]) : [];
  } catch {
    return [];
  }
}

export function useLocalExportHistory() {
  const [history, setHistory] = useState<LocalExportHistoryItem[]>(readHistory);

  useEffect(() => {
    localStorage.setItem(historyKey, JSON.stringify(history.slice(0, 30)));
  }, [history]);

  function addHistoryItem(item: Omit<LocalExportHistoryItem, "id" | "completedAt">) {
    setHistory((current) => [
      {
        ...item,
        id: crypto.randomUUID(),
        completedAt: new Date().toISOString(),
      },
      ...current,
    ]);
  }

  return { history, addHistoryItem };
}
