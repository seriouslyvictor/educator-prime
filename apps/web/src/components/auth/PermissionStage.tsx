import { FolderOpen, GraduationCap, ShieldCheck } from "lucide-react";

import { AccountChip } from "./AccountChip";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import type { AuthState } from "@/types";

export function PermissionStage({
  auth,
  busy,
  capability,
  partialConsent,
  onGrant,
  onLogout,
}: {
  auth: AuthState | null;
  busy: boolean;
  capability: "classroom" | "drive";
  partialConsent: boolean;
  onGrant: () => void;
  onLogout: () => void;
}) {
  const isDrive = capability === "drive";
  const Icon = isDrive ? FolderOpen : GraduationCap;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-2xl">
        <CardHeader className="gap-4">
          <AccountChip auth={auth} />
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-2xl bg-muted">
              <Icon />
            </div>
            <div>
              <CardTitle>{isDrive ? "Permitir leitura do Drive" : "Permitir leitura do Classroom"}</CardTitle>
              <CardDescription>
                {isDrive
                  ? "O Drive só é usado para ler anexos das entregas selecionadas."
                  : "O Classroom permite listar suas turmas, atividades e entregas de alunos."}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {partialConsent ? (
            <Alert variant="default">
              <ShieldCheck />
              <AlertTitle>Permissão incompleta</AlertTitle>
              <AlertDescription>
                Marque todas as caixas solicitadas na tela do Google para continuar.
              </AlertDescription>
            </Alert>
          ) : null}
          <Separator />
          <ul className="flex flex-col gap-3 text-sm text-muted-foreground">
            <li>Somente leitura: o app não altera Classroom nem Drive.</li>
            <li>Você pode trocar de conta se estiver usando um perfil pessoal.</li>
            <li>Organizações podem bloquear apps externos; nesse caso, o gate explica o bloqueio.</li>
          </ul>
        </CardContent>
        <CardFooter className="gap-3">
          <Button onClick={onGrant} disabled={busy}>
            {busy ? <Spinner data-icon="inline-start" /> : <ShieldCheck data-icon="inline-start" />}
            {isDrive ? "Permitir Drive" : "Permitir Classroom"}
          </Button>
          <Button variant="outline" onClick={onLogout} disabled={busy}>
            Trocar de conta
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
