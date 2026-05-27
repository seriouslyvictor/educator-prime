import type { PreviewTreeNode } from "../lib/preview-tree";
import { AppIcon } from "./icons";
import { useState } from "react";

export function DryRunDrawer({
  tree,
  fileCount,
  deliveryMode,
  onClose,
  onProceed,
}: {
  tree: PreviewTreeNode;
  fileCount: number;
  deliveryMode: "folder" | "zip";
  onClose: () => void;
  onProceed: () => void;
}) {
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <aside className="drawer">
        <div className="drawer-head">
          <div>
            <div className="drawer-title">Prévia da exportação</div>
            <div className="drawer-sub">
              {fileCount ? `${fileCount} arquivos estão prontos no manifesto atual.` : "Os arquivos exatos são resolvidos quando a exportação começa."}
            </div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Fechar">
            <AppIcon name="x" />
          </button>
        </div>
        <div className="drawer-body">
          <TreeNode node={tree} />
        </div>
        <div className="drawer-foot">
          <button className="btn btn-ghost" onClick={onClose}>
            Voltar para seleção
            <span className="kbd kbd-light">Esc</span>
          </button>
          <button className="btn btn-primary" onClick={onProceed} disabled={deliveryMode === "zip"}>
            <AppIcon name="download" />
            {deliveryMode === "zip" ? ".zip ainda é placeholder" : "Tudo certo, baixar"}
          </button>
        </div>
      </aside>
    </>
  );
}

function TreeNode({ node, depth = 0 }: { node: PreviewTreeNode; depth?: number }) {
  const [open, setOpen] = useState(depth < 2);
  const indent = Array.from({ length: depth }).map((_, index) => (
    <span className="tree-indent" key={index} />
  ));

  if (node.type === "note") {
    return (
      <div className="tree-node note">
        {indent}
        <span className="tree-spacer" />
        {node.name}
      </div>
    );
  }

  if (node.type === "dir") {
    return (
      <>
        <button className="tree-node dir" onClick={() => setOpen((current) => !current)}>
          {indent}
          <AppIcon name={open ? "chevronDown" : "chevronRight"} />
          <AppIcon name={open ? "folderOpen" : "folder"} />
          <span>{node.name}</span>
          <span className="tree-count">{node.children?.length ?? 0} itens</span>
        </button>
        {open ? node.children?.map((child, index) => <TreeNode node={child} depth={depth + 1} key={`${child.name}-${index}`} />) : null}
      </>
    );
  }

  return (
    <div className="tree-node">
      {indent}
      <span className="tree-spacer" />
      <AppIcon name="fileText" />
      <span>{node.name}</span>
    </div>
  );
}
