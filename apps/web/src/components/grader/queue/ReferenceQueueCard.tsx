import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { GradingQueueItem, QueueAction } from "../../../types";
import { AppIcon } from "../../icons";
import { queueItemKey, isDestructiveAction, actionsForItem, referenceQueueStatus } from "./queueActions";

export function ReferenceQueueSection({
  title,
  count,
  items,
  manageMode,
  selectedKeys,
  onToggleSelect,
  onAction,
  onPick,
}: {
  title: string;
  count: number;
  items: GradingQueueItem[];
  manageMode: boolean;
  selectedKeys: string[];
  onToggleSelect: (item: GradingQueueItem) => void;
  onAction: (action: QueueAction, items: GradingQueueItem[]) => void;
  onPick: (item: GradingQueueItem) => void;
}) {
  return (
    <section>
      <div className="queue-section-head">
        <h2>{title}</h2>
        <span className="count">{count}</span>
      </div>
      <div className="queue-grid">
        {items.map((item) => (
          <ReferenceQueueCard
            key={`${item.course_id}-${item.activity_id}-${item.latest_job_id ?? "new"}`}
            item={item}
            manageMode={manageMode}
            selected={selectedKeys.includes(queueItemKey(item))}
            onToggleSelect={onToggleSelect}
            onAction={onAction}
            onPick={onPick}
          />
        ))}
      </div>
    </section>
  );
}

function ReferenceQueueCard({
  item,
  manageMode,
  selected,
  onToggleSelect,
  onAction,
  onPick,
}: {
  item: GradingQueueItem;
  manageMode: boolean;
  selected: boolean;
  onToggleSelect: (item: GradingQueueItem) => void;
  onAction: (action: QueueAction, items: GradingQueueItem[]) => void;
  onPick: (item: GradingQueueItem) => void;
}) {
  const total = item.total_submissions || item.submission_count || 0;
  const reviewed = item.reviewed_submissions || 0;
  const pct = total > 0 ? Math.min(100, (reviewed / total) * 100) : 0;
  const status = referenceQueueStatus(item);
  const featured = status.cls === "ai" || status.cls === "drafting";
  const [menuOpen, setMenuOpen] = useState(false);
  const className = [
    "queue-card",
    featured ? "featured" : "",
    menuOpen ? "menu-open" : "",
    manageMode ? "managing" : "",
    selected ? "selected" : "",
  ].filter(Boolean).join(" ");
  const activate = () => {
    if (manageMode) {
      onToggleSelect(item);
      return;
    }
    onPick(item);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    activate();
  };

  return (
    <div
      className={className}
      role="button"
      tabIndex={0}
      onClick={activate}
      onKeyDown={onKeyDown}
      aria-pressed={manageMode ? selected : undefined}
    >
      <div className="queue-card-top">
        {manageMode ? (
          <span className={`qc-check${selected ? " on" : ""}`} aria-hidden="true">
            {selected ? <AppIcon name="check" /> : null}
          </span>
        ) : null}
        <div className="queue-card-copy">
          <div className="queue-course">
            <span className="dot" />
            {item.course_name}
          </div>
          <h3 className="queue-card-title">{item.activity_title}</h3>
        </div>
        <div className="qc-top-right">
          <span className={`qc-pill ${status.cls}`}>
            <AppIcon name={status.icon} />
            {status.label}
          </span>
          {!manageMode ? (
            <CardMenu item={item} onAction={onAction} onOpenChange={setMenuOpen} />
          ) : null}
        </div>
      </div>

      <div className="queue-card-meta">
        <span>Atividade</span>
        {item.due_label ? (
          <>
            <span className="sep" />
            <span>{item.due_label}</span>
          </>
        ) : null}
        <span className="sep" />
        <span>{item.submission_count} entregas</span>
      </div>

      <div className="queue-card-progress">
        <div className="qcp-bar">
          <div className={`qcp-bar-fill ${status.cls === "ai" ? "ai" : ""}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="qcp-label">
          {reviewed}/{total} revisadas
        </span>
      </div>

      <div className="queue-card-footer">
        <span className="queue-card-note">
          {status.cls === "posted" ? "Rascunhos concluídos" : <><span className="ai-glyph">✦</span> pronto para IA</>}
        </span>
        {!manageMode ? (
          <span className="qc-cta">
            {status.cta}
            <AppIcon name="chevronRight" />
          </span>
        ) : null}
      </div>
    </div>
  );
}

function CardMenu({
  item,
  onAction,
  onOpenChange,
}: {
  item: GradingQueueItem;
  onAction: (action: QueueAction, items: GradingQueueItem[]) => void;
  onOpenChange: (open: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [arming, setArming] = useState<QueueAction | null>(null);
  const ref = useRef<HTMLDivElement | null>(null);
  const setMenuOpen = (value: boolean) => {
    setOpen(value);
    setArming(null);
    onOpenChange(value);
  };

  useEffect(() => {
    if (!open) return;
    const onDoc = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setMenuOpen(false);
    };
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const run = (action: QueueAction) => {
    // TODO: shadcn AlertDialog in the app-wide migration.
    if (isDestructiveAction(action) && arming !== action) {
      setArming(action);
      return;
    }
    setMenuOpen(false);
    onAction(action, [item]);
  };

  return (
    <div className="qc-menu-wrap" ref={ref} onClick={(event) => event.stopPropagation()}>
      <button
        className="qc-kebab"
        aria-expanded={open}
        aria-label="Gerenciar atividade"
        title="Gerenciar atividade"
        onClick={() => setMenuOpen(!open)}
      >
        <AppIcon name="moreHorizontal" />
      </button>
      {open ? (
        <div className="qc-menu" role="menu">
          <div className="qc-menu-head">Gerenciar</div>
          {actionsForItem(item).map((action) => {
            const armed = arming === action.id;
            const confirmCopy =
              action.id === "restart"
                ? "Reiniciar e reprocessar tudo?"
                : "Remover esta atividade?";
            return (
              <button
                key={action.id}
                role="menuitem"
                className={`qc-menu-item${armed ? " armed" : ""}`}
                onClick={() => run(action.id)}
              >
                <AppIcon name={armed ? "triangleAlert" : action.icon} />
                <span className="qmi-text">
                  <span className="qmi-label">{armed ? confirmCopy : action.label}</span>
                  <span className="qmi-sub">
                    {armed ? "clique de novo para confirmar" : action.sub}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
