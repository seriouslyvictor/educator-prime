import { useState } from "react";
import type { GradingQueueItem, QueueAction } from "../../types";
import { AppIcon } from "../icons";
import { SearchBox } from "../ui";
import { queueItemKey, isDestructiveAction, isQueueActionValid, bulkActions } from "./queue/queueActions";
import { ReferenceQueueSection } from "./queue/ReferenceQueueCard";
import { ArchivedSection } from "./queue/ArchivedSection";
import graderStyles from "./Grader.module.css";
import "./GraderQueue.module.css";
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

export { referenceQueueStatus } from "./queue/queueActions";


