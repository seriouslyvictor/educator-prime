import type { ButtonHTMLAttributes, HTMLAttributes } from "react";
import { resolveError } from "../lib/errorCatalog";
import { AppIcon } from "./icons";
import uiStyles from "./ui.module.css";
import { cn } from "../lib/utils";
void uiStyles;

export { cn };

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <section className={cn(uiStyles.card, className)} {...props} />;
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card-header", className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("card-title", className)} {...props} />;
}

export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("card-description", className)} {...props} />;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card-content", className)} {...props} />;
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card-footer", className)} {...props} />;
}

export function Tabs({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("tabs", className)} {...props} />;
}

export function TabsList({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("tabs-list", className)} role="tablist" {...props} />;
}

export function TabsTrigger({
  className,
  active,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      className={cn("tabs-trigger", active && "active", className)}
      role="tab"
      aria-selected={active}
      {...props}
    />
  );
}

export function RadioGroup({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("radio-group", className)} role="radiogroup" {...props} />;
}

export function RadioItem({
  className,
  active,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      className={cn("radio-item", active && "active", className)}
      role="radio"
      aria-checked={active}
      {...props}
    >
      <span className="radio-dot" aria-hidden="true" />
      <span className="radio-copy">{children}</span>
    </button>
  );
}

export function SearchBox({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <div className={uiStyles.search}>
      <AppIcon name="search" />
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  copy,
}: {
  icon: "search" | "file" | "folderOpen" | "history";
  title: string;
  copy: string;
}) {
  return (
    <div className={uiStyles["empty-state"]}>
      <AppIcon name={icon} />
      <h3>{title}</h3>
      <p>{copy}</p>
    </div>
  );
}

export function SkeletonRows({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, index) => (
        <div className={uiStyles["skeleton-row"]} key={index} />
      ))}
    </>
  );
}

export function InlineError({
  error,
  message,
  onAction,
}: {
  error?: unknown;
  message?: unknown;
  onAction?: () => void;
}) {
  const entry = resolveError(error ?? message);
  return (
    <div className={`inline-error inline-error-${entry.tone}`} role="alert">
      <AppIcon name={entry.icon} />
      <div className="inline-error-copy">
        <strong>{entry.title}</strong>
        <span>{entry.body}</span>
        {entry.adminHint ? <span>Se persistir, avise o administrador.</span> : null}
        {entry.technicalDetail ? (
          <details>
            <summary>detalhes técnicos</summary>
            <code>{entry.technicalDetail}</code>
          </details>
        ) : null}
      </div>
      {entry.action && entry.action.kind !== "none" && onAction ? (
        <button className="btn btn-ghost" type="button" onClick={onAction}>
          {entry.action.label}
        </button>
      ) : null}
    </div>
  );
}
