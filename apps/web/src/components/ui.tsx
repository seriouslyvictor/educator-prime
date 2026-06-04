import type { ButtonHTMLAttributes, HTMLAttributes } from "react";
import { AppIcon } from "./icons";
import uiStyles from "./ui.module.css";
void uiStyles;

export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

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
