import { resolveError } from "../../lib/errorCatalog";
import { AppIcon } from "../icons";
import { Button } from "../ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../ui/card";

export function FullError({
  error,
  onAction,
}: {
  error: unknown;
  onAction?: () => void;
}) {
  const entry = resolveError(error);
  return (
    <div className="grid min-h-screen place-items-center bg-background p-6">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <div className="mb-2 flex size-10 items-center justify-center rounded-xl bg-muted text-foreground">
            <AppIcon name={entry.icon} />
          </div>
          <CardTitle>{entry.title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">{entry.body}</p>
          {entry.adminHint ? (
            <p className="text-sm text-muted-foreground">
              Se persistir, avise o administrador.
            </p>
          ) : null}
          {entry.technicalDetail ? (
            <details className="text-xs text-muted-foreground">
              <summary>detalhes técnicos</summary>
              <code className="break-words">{entry.technicalDetail}</code>
            </details>
          ) : null}
        </CardContent>
        {entry.action && entry.action.kind !== "none" ? (
          <CardFooter>
            <Button onClick={onAction ?? (() => window.location.reload())}>
              {entry.action.label}
            </Button>
          </CardFooter>
        ) : null}
      </Card>
    </div>
  );
}
