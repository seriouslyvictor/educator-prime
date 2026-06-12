import { FullError } from "./FullError";

export function Gate({ error, onAction }: { error: unknown; onAction?: () => void }) {
  return <FullError error={error} onAction={onAction} />;
}
