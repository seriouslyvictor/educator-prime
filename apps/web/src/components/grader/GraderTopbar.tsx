import type { ReactNode } from "react";
import graderStyles from "./Grader.module.css";
void graderStyles;

export function GraderTopbar({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action: ReactNode;
}) {
  return (
    <header className="grader-topbar">
      <div>
        <div className="grader-title">{title}</div>
        <div className="grader-subtitle">{subtitle}</div>
      </div>
      <div className="grader-actions">{action}</div>
    </header>
  );
}

