import { useState } from "react";
import { AppIcon } from "../../icons";
import type { GradingQueueItem, QueueAction } from "../../../types";
import { queueItemKey } from "./queueActions";

export function ArchivedSection({
  items,
  onAction,
}: {
  items: GradingQueueItem[];
  onAction: (action: QueueAction, items: GradingQueueItem[]) => void;
}) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;
  return (
    <section className="queue-archived">
      <button className="qa-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        <AppIcon name={open ? "chevronDown" : "chevronRight"} />
        Arquivadas e ocultas
        <span className="qa-count">{items.length}</span>
        <span className="qa-hint">
          <AppIcon name="history" /> seção local da fila
        </span>
      </button>
      {open ? (
        <div className="qa-list">
          {items.map((item) => (
            <div className="qa-row" key={queueItemKey(item)}>
              <span className="dot" />
              <span className="qa-title">{item.activity_title}</span>
              <span className="qa-course">{item.course_name}</span>
              <span className="qa-state">
                <AppIcon name={item.queue_state === "archived" ? "archive" : "eyeOff"} />
                {item.queue_state === "archived" ? "Arquivada" : "Oculta"}
              </span>
              <button className="qa-restore" onClick={() => onAction("restore", [item])}>
                <AppIcon name="refresh" /> Restaurar
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
