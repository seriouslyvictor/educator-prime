import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { GradingQueueItem, QueueAction } from "../../types";
import { AppIcon } from "../icons";
import { SearchBox } from "../ui";
import graderStyles from "./Grader.module.css";
void graderStyles;

export function GraderQueue({
  items,
  archivedItems,
  loading,
  onRefresh,
  onSetup,
  onOpenJob,
  onAction,
  onDownloadInstead,
}: {
  items: GradingQueueItem[];
  archivedItems: GradingQueueItem[];
  loading: boolean;
  onRefresh?: () => void;
  onSetup: (item: GradingQueueItem) => void;
  onOpenJob: (jobId: string) => void;
  onAction: (action: QueueAction, items: GradingQueueItem[]) => void;
  onDownloadInstead: () => void;
}) {
  const [query, setQuery] = useState("");
  const [manageMode, setManageMode] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [bulkArming, setBulkArming] = useState<QueueAction | null>(null);
  const filtered = items.filter((item) =>
    `${item.course_name} ${item.activity_title}`.toLowerCase().includes(query.toLowerCase()),
  );
  const drafting = filtered.filter((item) => item.latest_job_id && item.status !== "completed");
  const ready = filtered.filter((item) => !item.latest_job_id);
  const completed = filtered.filter((item) => item.status === "completed");
  const hasItems = items.length > 0;
  const hasRecoverableItems = archivedItems.length > 0;
  const hasFilteredItems = filtered.length > 0;
  const selectedItems = filtered.filter((item) => selectedKeys.includes(queueItemKey(item)));
  const selectedValidCount = (action: QueueAction) =>
    selectedItems.filter((item) => isQueueActionValid(action, item)).length;
  const toggleSelect = (item: GradingQueueItem) => {
    const key = queueItemKey(item);
    setSelectedKeys((current) =>
      current.includes(key) ? current.filter((value) => value !== key) : [...current, key],
    );
    setBulkArming(null);
  };
  const runBulkAction = (action: QueueAction) => {
    const validItems = selectedItems.filter((item) => isQueueActionValid(action, item));
    if (validItems.length === 0) return;
    // TODO: shadcn AlertDialog in the app-wide migration.
    if (isDestructiveAction(action) && bulkArming !== action) {
      setBulkArming(action);
      return;
    }
    onAction(action, validItems);
    setSelectedKeys([]);
    setBulkArming(null);
    setManageMode(false);
  };
  const toggleManageMode = () => {
    setManageMode((current) => !current);
    setSelectedKeys([]);
    setBulkArming(null);
  };

  return (
    <div className={graderStyles["g-page"]} data-screen-label="01 Grader - Queue">
      <div className="g-topbar">
        <div>
          <div className="g-crumb">
            <span>
              <span className="ai-glyph">✦</span> Corrigir com IA
            </span>
          </div>
          <h1 className="g-title">O que você quer corrigir?</h1>
          <div className="g-subtitle">
            {hasItems || hasRecoverableItems
              ? `${items.length} atividades ativas pela IA`
              : "Envie uma atividade pela tela de Turmas para preparar a correção com IA. Isso não é um erro."}
          </div>
        </div>
        <div className="g-topbar-actions">
          {hasItems ? (
            <SearchBox value={query} onChange={setQuery} placeholder="Filtrar atividades..." />
          ) : null}
          <div className="g-actions">
            {hasItems ? (
              <button className={`btn btn-secondary${manageMode ? " manage-on" : ""}`} onClick={toggleManageMode}>
                <AppIcon name={manageMode ? "check" : "listChecks"} />
                {manageMode ? "Concluir" : "Gerenciar"}
              </button>
            ) : null}
            <button className="btn btn-secondary" onClick={onDownloadInstead}>
              <AppIcon name="download" /> Baixar em vez disso
            </button>
            {onRefresh ? (
              <button className="btn btn-primary" onClick={onRefresh} disabled={loading}>
                <AppIcon name={loading ? "loader" : "refresh"} className={loading ? "ico spin" : "ico"} />
                Atualizar
              </button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="queue-wrap">
        {!hasItems && !hasRecoverableItems ? (
          <div className="ai-empty-state">
            <div className="ai-empty-badge">
              <AppIcon name="sparkle" />
            </div>
            <h2>Nenhuma atividade na fila de IA</h2>
            <p>
              Escolha uma turma, encontre a atividade desejada e clique em Corrigir com IA.
              A auditoria de privacidade e os rascunhos aparecerão aqui quando a fila começar.
            </p>
            <div className="ai-empty-actions">
              <button className="btn btn-primary" onClick={onDownloadInstead}>
                <AppIcon name="classroom" /> Ir para Turmas
              </button>
            </div>
          </div>
        ) : hasItems && !hasFilteredItems ? (
          <div className="queue-empty">Nenhuma atividade corresponde a "{query}".</div>
        ) : (
          <>
            {drafting.length > 0 ? (
              <ReferenceQueueSection
                title="Continue de onde parou"
                count={drafting.length}
                items={drafting}
                manageMode={manageMode}
                selectedKeys={selectedKeys}
                onToggleSelect={toggleSelect}
                onAction={onAction}
                onPick={(item) => item.latest_job_id && onOpenJob(item.latest_job_id)}
              />
            ) : null}
            {ready.length > 0 ? (
              <ReferenceQueueSection
                title="Prontas para rascunho com IA"
                count={ready.length}
                items={ready}
                manageMode={manageMode}
                selectedKeys={selectedKeys}
                onToggleSelect={toggleSelect}
                onAction={onAction}
                onPick={onSetup}
              />
            ) : null}
            {completed.length > 0 ? (
              <ReferenceQueueSection
                title="Conjuntos concluídos"
                count={completed.length}
                items={completed}
                manageMode={manageMode}
                selectedKeys={selectedKeys}
                onToggleSelect={toggleSelect}
                onAction={onAction}
                onPick={(item) => item.latest_job_id && onOpenJob(item.latest_job_id)}
              />
            ) : null}
            <ArchivedSection items={archivedItems} onAction={onAction} />
          </>
        )}
      </div>
      {manageMode ? (
        <div className="qc-bulkbar" role="toolbar" aria-label="Ações em massa">
          <span className="qb-count">
            {selectedKeys.length} selecionada{selectedKeys.length === 1 ? "" : "s"}
          </span>
          <span className="qb-sep" />
          {bulkActions.map((action) => {
            const validCount = selectedValidCount(action.id);
            const armed = bulkArming === action.id;
            return (
              <button
                key={action.id}
                disabled={validCount === 0}
                onClick={() => runBulkAction(action.id)}
                title={validCount === 0 ? "Nenhum item selecionado permite esta ação" : action.sub}
              >
                <AppIcon name={armed ? "triangleAlert" : action.icon} />
                {armed ? action.confirmLabel : action.bulkLabel}
              </button>
            );
          })}
          <button
            className="qb-close"
            aria-label="Sair do modo gerenciar"
            onClick={() => {
              setManageMode(false);
              setSelectedKeys([]);
              setBulkArming(null);
            }}
          >
            <AppIcon name="x" />
          </button>
        </div>
      ) : null}
    </div>
  );
}

function ReferenceQueueSection({
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

type QueueActionConfig = {
  id: QueueAction;
  label: string;
  bulkLabel: string;
  confirmLabel: string;
  sub: string;
  icon: "refresh" | "trash" | "archive" | "eyeOff";
};

const bulkActions: QueueActionConfig[] = [
  {
    id: "restart",
    label: "Reiniciar do zero",
    bulkLabel: "Reiniciar",
    confirmLabel: "Confirmar reinício",
    sub: "descarta rascunhos, notas, critérios e auditoria",
    icon: "refresh",
  },
  {
    id: "remove",
    label: "Remover da fila",
    bulkLabel: "Remover",
    confirmLabel: "Confirmar remoção",
    sub: "continua disponível em Atividades",
    icon: "trash",
  },
  {
    id: "archive",
    label: "Arquivar",
    bulkLabel: "Arquivar",
    confirmLabel: "Arquivar",
    sub: "sai da fila e fica nesta seção",
    icon: "archive",
  },
  {
    id: "hide",
    label: "Ocultar da visualização",
    bulkLabel: "Ocultar",
    confirmLabel: "Ocultar",
    sub: "acessível pela seção de arquivadas e ocultas",
    icon: "eyeOff",
  },
];

function queueItemKey(item: GradingQueueItem) {
  return `${item.course_id}-${item.activity_id}-${item.latest_job_id ?? "new"}`;
}

function isDestructiveAction(action: QueueAction) {
  return action === "restart" || action === "remove";
}

function isQueueActionValid(action: QueueAction, item: GradingQueueItem) {
  if (action === "remove") return true;
  if (action === "restore") return Boolean(item.latest_job_id);
  return Boolean(item.latest_job_id);
}

function actionsForItem(item: GradingQueueItem) {
  if (!item.latest_job_id) return bulkActions.filter((action) => action.id === "remove");
  return bulkActions;
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

function ArchivedSection({
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

export function referenceQueueStatus(item: GradingQueueItem): {
  label: string;
  cls: string;
  icon: "sparkle" | "eye" | "settings" | "checkCircle";
  cta: string;
} {
  if (item.status === "completed") return { label: "Concluída", cls: "posted", icon: "checkCircle", cta: "Abrir" };
  if (item.status === "reviewing") return { label: "Em revisão", cls: "reviewing", icon: "eye", cta: "Revisar" };
  if (item.latest_job_id) return { label: "Rascunhando", cls: "drafting", icon: "settings", cta: "Retomar" };
  return { label: "IA pronta", cls: "ai", icon: "sparkle", cta: "Começar" };
}


