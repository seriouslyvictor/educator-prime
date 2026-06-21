import { CheckCircle2, GraduationCap, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";

const steps = [
  "Conecte sua conta Google escolar",
  "Escolha turma e atividade",
  "Exporte entregas ou corrija com IA",
];

export function LoginScreen({
  connecting,
  onConnect,
}: {
  connecting: boolean;
  onConnect: () => void;
}) {
  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[1fr_440px]">
      <section className="flex flex-col justify-between gap-12 p-8 lg:p-12">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
            <GraduationCap />
          </div>
          <div>
            <div className="font-heading text-lg font-semibold">Classroom Downloader</div>
            <div className="text-sm text-muted-foreground">Correção e exportação para professores</div>
          </div>
        </div>

        <div className="max-w-2xl">
          <p className="text-sm font-medium text-muted-foreground">Google OAuth seguro</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight text-foreground lg:text-5xl">
            Comece pela conta certa antes de corrigir qualquer turma.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-muted-foreground">
            O app usa permissões incrementais do Google para abrir apenas o que precisa:
            identidade, Classroom e Drive em somente leitura.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          {steps.map((step, index) => (
            <Card key={step} size="sm">
              <CardHeader>
                <CardTitle>{index + 1}. {step}</CardTitle>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>

      <aside className="flex items-center justify-center border-l bg-muted/30 p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Entrar no app</CardTitle>
            <CardDescription>
              Use uma conta Google com acesso ao Classroom. Não existe senha local neste app.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <Button size="lg" onClick={onConnect} disabled={connecting}>
              {connecting ? <Spinner data-icon="inline-start" /> : <ShieldCheck data-icon="inline-start" />}
              Continuar com o Google
            </Button>
            <Separator />
            <div className="flex flex-col gap-3 text-sm text-muted-foreground">
              <div className="flex gap-2">
                <CheckCircle2 data-icon="inline-start" />
                Nunca apagamos nem modificamos dados no Google.
              </div>
              <div className="flex gap-2">
                <CheckCircle2 data-icon="inline-start" />
                Turmas sem Classroom recebem uma explicação dedicada.
              </div>
            </div>
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}
