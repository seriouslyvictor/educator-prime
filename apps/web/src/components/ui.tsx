import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export function Button({
  className,
  variant = "default",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "outline" | "ghost" | "danger";
}) {
  return <button className={cn("button", `button-${variant}`, className)} {...props} />;
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <section className={cn("card", className)} {...props} />;
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

export function Badge({
  className,
  variant = "secondary",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { variant?: "secondary" | "success" | "warning" }) {
  return <span className={cn("badge", `badge-${variant}`, className)} {...props} />;
}

export function Progress({ value }: { value: number }) {
  return (
    <div className="progress" aria-label="Progress">
      <div className="progress-bar" style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
    </div>
  );
}

export function Empty({
  icon,
  title,
  description,
}: {
  icon?: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="empty">
      {icon ? <div className="empty-icon">{icon}</div> : null}
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}
