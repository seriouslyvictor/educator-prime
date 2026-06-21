import { Building2, DoorOpen, GraduationCap } from "lucide-react";

import { AccountChip } from "./AccountChip";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import type { AuthState } from "@/types";

const copy = {
  "no-courses": {
    icon: GraduationCap,
    title: "Nenhuma turma para corrigir",
    body: "Sua conta Google conectou, mas o Classroom não retornou turmas ativas para professor. Entre com a conta escolar usada para lecionar.",
  },
  "classroom-unavailable": {
    icon: GraduationCap,
    title: "Esta conta não tem acesso ao Classroom",
    body: "O Google informou que o tipo de conta conectado não pode usar o Classroom. Troque para uma conta escolar habilitada.",
  },
  "policy-blocked": {
    icon: Building2,
    title: "A organização bloqueou este app",
    body: "O administrador Google Workspace precisa liberar o acesso ao Classroom Downloader antes de você continuar.",
  },
};

export function AuthExplainer({
  stage,
  auth,
  onLogout,
}: {
  stage: keyof typeof copy;
  auth: AuthState | null;
  onLogout: () => void;
}) {
  const item = copy[stage];
  const Icon = item.icon;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <Empty className="max-w-xl border">
        <EmptyMedia variant="icon">
          <Icon />
        </EmptyMedia>
        <EmptyHeader>
          <EmptyTitle>{item.title}</EmptyTitle>
          <EmptyDescription>{item.body}</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <AccountChip auth={auth} />
          <Button onClick={onLogout}>
            <DoorOpen data-icon="inline-start" />
            Trocar de conta
          </Button>
        </EmptyContent>
      </Empty>
    </div>
  );
}
