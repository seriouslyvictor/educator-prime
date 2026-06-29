# Decisões e histórico

Este documento registra as decisões que moldam o Classroom Downloader, especialmente
as que já foram discutidas, testadas ou descartadas. A função dele é evitar que uma
pessoa, ou um agente, reabra o mesmo assunto sem uma informação nova de verdade.

Os planos completos ficam na pasta local `archive/`, com documentos numerados como
`001`, `002` e alguns planos nomeados. Essa pasta não é versionada no Git por opção:
é material de trabalho. Por isso, as decisões que ainda importam estão resumidas
aqui, dentro do repositório. Quando a `archive/` estiver disponível localmente, ela
serve como aprofundamento.

Para os limites atuais do produto, a referência viva é
[constraints.md](constraints.md).

---

## Decisões fechadas

### OAuth fica em Testing, com re-login a cada 7 dias

O escopo `drive.readonly` é restricted e necessário para o app funcionar. Por isso o
projeto fica preso ao modo Testing do OAuth do Google.

As alternativas já foram avaliadas. O tipo de usuário `Internal` não resolve porque o
SENAI é uma rede grande demais para uma ferramenta local de alguns professores. A
publicação externa com verificação CASA também foi descartada por custo e burocracia.

Consequência aceita: re-login semanal e limite de 100 usuários adicionados
manualmente. Detalhes em [constraints.md](constraints.md#sete-dias). Planos:
`archive/012`, `archive/014`.

### Consentimento de escopo é tudo de uma vez

Pedir permissões gradualmente já foi implementado e depois revertido no plano 013. O
fluxo quebrou o login e espalhou telas de permissão pelo uso normal do app.

A decisão atual é pedir todos os escopos necessários no login. Não reabra
consentimento incremental sem um motivo novo e concreto. Veja
[constraints.md](constraints.md). Plano: `archive/013`.

### O app não lança nota nem feedback no Classroom

Essa decisão vem de limite da API do Google, não de excesso de cautela. O app gera
rascunhos, organiza o trabalho e ajuda o professor com o PiP, mas quem lança a nota é
o professor.

A rota de bookmarklet ou automação de DOM dentro do Classroom foi considerada e
descartada em 2026-06-06 por fragilidade e custo de manutenção. Veja
[constraints.md](constraints.md). Planos:
`archive/classroom-grade-posting-assist-2026-06-06.md` e
`archive/023-guided-posting-first-student-link.md`.

### Office segue pela pista de texto

Arquivos Office passam pela extração textual. Conteúdo visual desenhado dentro de
`.docx`, `.xlsx` ou `.pptx` pode se perder.

Levar Office para a pista de visão exigiria uma conversão geral com LibreOffice
headless, como Office -> PDF -> visão. Essa abordagem foi evitada por complexidade e
custo operacional. É uma limitação conhecida, não um bug simples. Veja
[constraints.md](constraints.md#office-visual). Plano:
`archive/office-pdf-support-plan.md`.

### Nota por critério é a fonte da verdade

A nota final é a soma dos pontos por critério, salvos como inteiros. Ela não deve
confiar no número holístico que o modelo pode devolver em paralelo.

O pareamento dos pontos com os critérios é feito por posição, para resistir à
corrupção intermitente de acentos do Gemini. Veja
[grading-lifecycle.md](grading-lifecycle.md) e [constraints.md](constraints.md).
Planos: `archive/018-per-criterion-scores-and-progress-bars.md`, `archive/021`.

---

## Histórico por tema

Este mapa ajuda a encontrar o plano certo quando a pasta `archive/` estiver presente
na máquina.

### Correção com IA

- `ai-grading-layer.md`, `plan-grading-split.md` - desenho do motor de correção.
- `litellm-grading-execution-directive.md`,
  `litellm-grading-batch-intervention-plan.md` - integração LiteLLM.
- `plan-image-grading.md` - pista de visão para imagens e PDFs.
- `022-two-pass-outlier-flagging.md`, `024-isolate-outlier-review-failure.md` -
  segunda passada de outliers.
- `019-review-while-drafting.md`, `020-submission-preview-retry.md`,
  `025-preview-retry-e2e-coverage.md` - revisão durante o rascunho.
- `026-lazy-activity-grade-summaries.md` - resumos de nota sob demanda.
- `caching-strategy.md` - cache de download e de conteúdo.

### Google e autenticação

- `012-gradual-google-permissions.md`, `013-gradual-google-permissions.md` - escopo
  incremental, já rejeitado.
- `014-live-google-e2e.md`, `007-real-session-smoke-local.md` - testes com Google
  real.
- `015-standalone-login-screen.md` - tela de login separada.

### Privacidade e segurança

- `003-encrypt-oauth-credentials-at-rest.md` - credenciais criptografadas em
  repouso.

### Frontend e UX

- `005-decompose-app-tsx.md`, `008-decompose-grader-review.md`,
  `009-decompose-grader-setup-queue.md` - quebra de componentes grandes.
- `010-frontend-ui-conventions-guardrail.md`,
  `frontend-css-module-refactor-plan.md` - convenções de UI; veja `FRONTEND.md`.
- `011-implement-token-bridge.md`, `012-implement-token-bridge.md` - ponte de tokens
  shadcn; veja `apps/web/docs/token-bridge-findings.md`.
- `plan-error-screens.md` - telas e camadas de erro.
- `plan-queue-management.md` - gestão da fila: arquivar, ocultar e restaurar.
- `016-turmas-grade-awareness.md`, `017-hide-rubric-in-brief-mode.md` - ajustes de
  Turmas e modo simples.
- `design-alignment-directive-2026-06-06.md`, `papercuts-2026-06-07/`,
  `ux-audit-2026-06-04/` - alinhamento visual e papercuts.

### Observabilidade

- `logging-observability-plan.md`, `plan-observability.md`,
  `llm-payload-response-logging-research.md` - logs estruturados e auditoria de IA.

### Testes

- `001-frontend-test-lint-baseline.md`, `002-frontend-core-logic-tests.md`,
  `006-playwright-e2e-core-flows.md` - base de testes.
- `027-real-file-test-corpus.md` - corpus de arquivos reais, em `test_files/`.

### Infra

- `coolify-deploy.md` - promovido para [coolify-deploy.md](coolify-deploy.md), agora
  versionado.

> Observação: `plan.md` é o documento-mãe original. Partes dele já foram superadas
> pelos planos numerados e por estes documentos.
