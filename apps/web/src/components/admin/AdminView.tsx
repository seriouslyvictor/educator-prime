import { useEffect, useMemo, useState } from "react";
import { Search, ShieldCheck, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import type { AdminStats, AiAttemptItem, AiAttemptPayload, AppEventItem } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const PAGE_SIZE = 50;

type EventFilters = {
  level: string;
  area: string;
  query: string;
};

type AttemptFilters = {
  status: string;
  stage: string;
  retryable: string;
};

export function AdminView() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [events, setEvents] = useState<AppEventItem[]>([]);
  const [attempts, setAttempts] = useState<AiAttemptItem[]>([]);
  const [eventFilters, setEventFilters] = useState<EventFilters>({
    level: "all",
    area: "all",
    query: "",
  });
  const [attemptFilters, setAttemptFilters] = useState<AttemptFilters>({
    status: "all",
    stage: "all",
    retryable: "all",
  });
  const [eventsLoading, setEventsLoading] = useState(true);
  const [attemptsLoading, setAttemptsLoading] = useState(true);
  const [selectedEvent, setSelectedEvent] = useState<AppEventItem | null>(null);
  const [selectedAttempt, setSelectedAttempt] = useState<AiAttemptItem | null>(null);
  const [payload, setPayload] = useState<AiAttemptPayload | null>(null);
  const [payloadLoading, setPayloadLoading] = useState(false);

  useEffect(() => {
    void loadStats();
  }, []);

  useEffect(() => {
    void loadEvents();
  }, [eventFilters.level, eventFilters.area]);

  useEffect(() => {
    void loadAttempts();
  }, [attemptFilters.status, attemptFilters.stage, attemptFilters.retryable]);

  useEffect(() => {
    if (!selectedAttempt?.has_payload) {
      setPayload(null);
      return;
    }
    setPayloadLoading(true);
    api.adminGetAttemptPayload(selectedAttempt.id)
      .then(setPayload)
      .catch(() => setPayload(null))
      .finally(() => setPayloadLoading(false));
  }, [selectedAttempt]);

  const eventParams = useMemo(() => ({
    level: eventFilters.level === "all" ? undefined : eventFilters.level,
    event_prefix: eventFilters.area === "all" ? undefined : eventFilters.area,
    q: eventFilters.query || undefined,
    limit: PAGE_SIZE,
  }), [eventFilters]);

  const attemptParams = useMemo(() => ({
    status: attemptFilters.status === "all" ? undefined : attemptFilters.status,
    stage: attemptFilters.stage === "all" ? undefined : attemptFilters.stage,
    retryable: attemptFilters.retryable === "all" ? undefined : attemptFilters.retryable === "true",
    limit: PAGE_SIZE,
  }), [attemptFilters]);

  async function loadStats() {
    setStats(await api.adminGetStats());
  }

  async function loadEvents(before?: string) {
    setEventsLoading(true);
    try {
      const rows = await api.adminListEvents({ ...eventParams, before });
      setEvents((current) => before ? [...current, ...rows] : rows);
    } finally {
      setEventsLoading(false);
    }
  }

  async function loadAttempts(before?: string) {
    setAttemptsLoading(true);
    try {
      const rows = await api.adminListAttempts({ ...attemptParams, before });
      setAttempts((current) => before ? [...current, ...rows] : rows);
    } finally {
      setAttemptsLoading(false);
    }
  }

  async function refreshAll() {
    await Promise.all([loadStats(), loadEvents(), loadAttempts()]);
  }

  return (
    <section className="adminRoot mx-auto flex w-full max-w-7xl flex-col gap-5 px-6 py-6 text-foreground">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-2xl font-medium">Admin</h1>
          <p className="text-sm text-muted-foreground">
            Eventos persistidos e chamadas de IA para revisar falhas sem depender do console.
          </p>
        </div>
        <Button variant="outline" onClick={() => void refreshAll()}>
          <RotateCcw data-icon="inline-start" />
          Atualizar
        </Button>
      </header>

      <StatsCards stats={stats} />

      <Tabs defaultValue="events">
        <TabsList>
          <TabsTrigger value="events">Eventos</TabsTrigger>
          <TabsTrigger value="attempts">Chamadas de IA</TabsTrigger>
        </TabsList>

        <TabsContent value="events" className="flex flex-col gap-4">
          <EventFiltersView
            filters={eventFilters}
            onChange={setEventFilters}
            onSearch={() => void loadEvents()}
          />
          <EventsTable
            rows={events}
            loading={eventsLoading}
            onSelect={setSelectedEvent}
            onMore={() => void loadEvents(events.at(-1)?.created_at)}
          />
        </TabsContent>

        <TabsContent value="attempts" className="flex flex-col gap-4">
          <AttemptFiltersView filters={attemptFilters} onChange={setAttemptFilters} />
          <AttemptsTable
            rows={attempts}
            loading={attemptsLoading}
            onSelect={setSelectedAttempt}
            onMore={() => void loadAttempts(attempts.at(-1)?.created_at)}
          />
        </TabsContent>
      </Tabs>

      <EventSheet event={selectedEvent} onOpenChange={(open) => !open && setSelectedEvent(null)} />
      <AttemptSheet
        attempt={selectedAttempt}
        payload={payload}
        loading={payloadLoading}
        onOpenChange={(open) => !open && setSelectedAttempt(null)}
      />
    </section>
  );
}

function StatsCards({ stats }: { stats: AdminStats | null }) {
  const warning = stats?.events_24h_by_level.WARNING ?? 0;
  const error = stats?.events_24h_by_level.ERROR ?? 0;
  const info = stats?.events_24h_by_level.INFO ?? 0;
  const cards = [
    ["Eventos 24h", `${warning + error + info}`, `${error} erros · ${warning} avisos`],
    ["Chamadas IA 7d", `${stats?.attempts_7d ?? 0}`, "tentativas registradas"],
    ["Custo 7d", `${formatCost(stats?.cost_cents_7d ?? 0)}`, "estimado pelo ledger"],
    ["Falhas 7d", `${stats?.failures_7d ?? 0}`, "status failed"],
  ];
  return (
    <div className="grid gap-3 md:grid-cols-4">
      {cards.map(([title, value, description]) => (
        <Card key={title}>
          <CardHeader>
            <CardDescription>{title}</CardDescription>
            <CardTitle>{stats ? value : <Skeleton className="h-7 w-16" />}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function EventFiltersView({
  filters,
  onChange,
  onSearch,
}: {
  filters: EventFilters;
  onChange: (filters: EventFilters) => void;
  onSearch: () => void;
}) {
  return (
    <FieldGroup className="grid gap-3 md:grid-cols-[160px_180px_1fr_auto]">
      <Field>
        <FieldLabel>Nível</FieldLabel>
        <Select value={filters.level} onValueChange={(level) => onChange({ ...filters, level })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent><SelectGroup>
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="INFO">Info</SelectItem>
            <SelectItem value="WARNING">Aviso</SelectItem>
            <SelectItem value="ERROR">Erro</SelectItem>
          </SelectGroup></SelectContent>
        </Select>
      </Field>
      <Field>
        <FieldLabel>Área</FieldLabel>
        <Select value={filters.area} onValueChange={(area) => onChange({ ...filters, area })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent><SelectGroup>
            <SelectItem value="all">Todas</SelectItem>
            <SelectItem value="auth.">auth.</SelectItem>
            <SelectItem value="grading.">grading.</SelectItem>
            <SelectItem value="cache.">cache.</SelectItem>
            <SelectItem value="google.">google.</SelectItem>
          </SelectGroup></SelectContent>
        </Select>
      </Field>
      <Field>
        <FieldLabel>Busca</FieldLabel>
        <InputGroup>
          <InputGroupAddon><Search /></InputGroupAddon>
          <InputGroupInput
            value={filters.query}
            onChange={(event) => onChange({ ...filters, query: event.target.value })}
            onKeyDown={(event) => event.key === "Enter" && onSearch()}
            placeholder="texto em fields_json"
          />
        </InputGroup>
      </Field>
      <Field className="justify-end">
        <FieldLabel className="opacity-0">Buscar</FieldLabel>
        <Button type="button" onClick={onSearch}>
          <Search data-icon="inline-start" />
          Buscar
        </Button>
      </Field>
    </FieldGroup>
  );
}

function AttemptFiltersView({
  filters,
  onChange,
}: {
  filters: AttemptFilters;
  onChange: (filters: AttemptFilters) => void;
}) {
  return (
    <FieldGroup className="grid gap-3 md:grid-cols-3">
      <Field>
        <FieldLabel>Status</FieldLabel>
        <Select value={filters.status} onValueChange={(status) => onChange({ ...filters, status })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent><SelectGroup>
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="completed">Completa</SelectItem>
            <SelectItem value="failed">Falha</SelectItem>
            <SelectItem value="blocked">Bloqueada</SelectItem>
          </SelectGroup></SelectContent>
        </Select>
      </Field>
      <Field>
        <FieldLabel>Etapa</FieldLabel>
        <Select value={filters.stage} onValueChange={(stage) => onChange({ ...filters, stage })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent><SelectGroup>
            <SelectItem value="all">Todas</SelectItem>
            <SelectItem value="grading">Correção</SelectItem>
            <SelectItem value="extraction">Extração</SelectItem>
          </SelectGroup></SelectContent>
        </Select>
      </Field>
      <Field>
        <FieldLabel>Retry</FieldLabel>
        <Select value={filters.retryable} onValueChange={(retryable) => onChange({ ...filters, retryable })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent><SelectGroup>
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="true">Retryable</SelectItem>
            <SelectItem value="false">Sem retry</SelectItem>
          </SelectGroup></SelectContent>
        </Select>
      </Field>
    </FieldGroup>
  );
}

function EventsTable({
  rows,
  loading,
  onSelect,
  onMore,
}: {
  rows: AppEventItem[];
  loading: boolean;
  onSelect: (row: AppEventItem) => void;
  onMore: () => void;
}) {
  if (loading && rows.length === 0) return <TableSkeleton />;
  if (rows.length === 0) return <AdminEmpty title="Sem eventos" description="Nenhum evento bateu nos filtros atuais." />;
  return (
    <div className="flex flex-col gap-3">
      <Table>
        <TableHeader><TableRow>
          <TableHead>Horário</TableHead><TableHead>Nível</TableHead><TableHead>Evento</TableHead><TableHead>Usuário</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id} className="cursor-pointer" onClick={() => onSelect(row)}>
              <TableCell>{formatDate(row.created_at)}</TableCell>
              <TableCell><LevelBadge level={row.level} /></TableCell>
              <TableCell className="font-mono text-xs">{row.event}</TableCell>
              <TableCell>{row.user_email ?? "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Button variant="outline" disabled={loading} onClick={onMore}>
        {loading ? <Spinner data-icon="inline-start" /> : null}
        Carregar mais
      </Button>
    </div>
  );
}

function AttemptsTable({
  rows,
  loading,
  onSelect,
  onMore,
}: {
  rows: AiAttemptItem[];
  loading: boolean;
  onSelect: (row: AiAttemptItem) => void;
  onMore: () => void;
}) {
  if (loading && rows.length === 0) return <TableSkeleton />;
  if (rows.length === 0) return <AdminEmpty title="Sem chamadas" description="Nenhuma chamada de IA bateu nos filtros atuais." />;
  return (
    <div className="flex flex-col gap-3">
      <Table>
        <TableHeader><TableRow>
          <TableHead>Horário</TableHead><TableHead>Job</TableHead><TableHead>Etapa</TableHead><TableHead>Modelo</TableHead><TableHead>Status</TableHead><TableHead>Tokens</TableHead><TableHead>Custo</TableHead><TableHead>Latência</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id} className="cursor-pointer" onClick={() => onSelect(row)}>
              <TableCell>{formatDate(row.created_at)}</TableCell>
              <TableCell className="font-mono text-xs">{shortId(row.job_id)}</TableCell>
              <TableCell>{stageLabel(row.stage)}</TableCell>
              <TableCell>{row.model ?? row.engine}</TableCell>
              <TableCell><StatusBadges row={row} /></TableCell>
              <TableCell>{row.token_count ?? "—"}</TableCell>
              <TableCell>{formatCost(row.cost_cents)}</TableCell>
              <TableCell>{row.latency_ms ? `${row.latency_ms}ms` : "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Button variant="outline" disabled={loading} onClick={onMore}>
        {loading ? <Spinner data-icon="inline-start" /> : null}
        Carregar mais
      </Button>
    </div>
  );
}

function EventSheet({ event, onOpenChange }: { event: AppEventItem | null; onOpenChange: (open: boolean) => void }) {
  return (
    <Sheet open={Boolean(event)} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-4 overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>{event?.event ?? "Evento"}</SheetTitle>
          <SheetDescription>{event ? `${event.level} · ${formatDate(event.created_at)}` : ""}</SheetDescription>
        </SheetHeader>
        {event ? (
          <div className="flex flex-col gap-4 px-6 pb-6">
            <Detail label="Logger" value={event.logger_name} />
            <Detail label="Usuário" value={event.user_email ?? "—"} />
            <Detail label="Request" value={event.request_id ?? "—"} />
            <Separator />
            <PreBlock value={prettyJson(event.fields_json)} />
            {event.exc_text ? <PreBlock value={event.exc_text} /> : null}
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function AttemptSheet({
  attempt,
  payload,
  loading,
  onOpenChange,
}: {
  attempt: AiAttemptItem | null;
  payload: AiAttemptPayload | null;
  loading: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Sheet open={Boolean(attempt)} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-4 overflow-y-auto sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle>{attempt ? `Chamada ${shortId(attempt.id)}` : "Chamada de IA"}</SheetTitle>
          <SheetDescription>{attempt ? `${stageLabel(attempt.stage)} · ${attempt.status}` : ""}</SheetDescription>
        </SheetHeader>
        {attempt ? (
          <div className="flex flex-col gap-4 px-6 pb-6">
            <div className="grid gap-3 md:grid-cols-2">
              <Detail label="Job" value={attempt.job_id} />
              <Detail label="Submission" value={attempt.submission_id} />
              <Detail label="Modelo" value={attempt.model ?? attempt.engine} />
              <Detail label="Erro" value={attempt.safe_error ?? "—"} />
            </div>
            <Separator />
            {loading ? <TableSkeleton /> : payload ? (
              <>
                <Detail label="Prompt" value="" />
                <PreBlock value={payload.prompt_text} />
                <Detail label="Resposta" value="" />
                <PreBlock value={payload.response_text ?? "(sem resposta registrada)"} />
              </>
            ) : (
              <AdminEmpty title="Payload indisponível" description="O payload foi purgado ou o logging estava desligado." />
            )}
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function TableSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  );
}

function AdminEmpty({ title, description }: { title: string; description: string }) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon"><ShieldCheck /></EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

function LevelBadge({ level }: { level: string }) {
  return <Badge variant={level === "ERROR" ? "destructive" : "secondary"}>{level}</Badge>;
}

function StatusBadges({ row }: { row: AiAttemptItem }) {
  return (
    <div className="flex flex-wrap gap-1">
      <Badge variant={row.status === "failed" ? "destructive" : "secondary"}>{row.status}</Badge>
      {row.retryable ? <Badge variant="outline">retry</Badge> : null}
      {row.safe_error ? <Badge variant="outline">{row.safe_error}</Badge> : null}
      {row.has_payload ? <Badge variant="secondary">payload</Badge> : null}
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className="break-all text-sm">{value}</div>
    </div>
  );
}

function PreBlock({ value }: { value: string }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-xl bg-muted p-3 text-xs leading-relaxed text-foreground">
      {value}
    </pre>
  );
}

function prettyJson(value: string) {
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("pt-BR");
}

function formatCost(value: number | null | undefined) {
  return value == null ? "—" : `${value.toFixed(4)}¢`;
}

function shortId(value: string) {
  return value.slice(0, 8);
}

function stageLabel(stage: string) {
  return stage === "extraction" ? "Extração" : "Correção";
}
