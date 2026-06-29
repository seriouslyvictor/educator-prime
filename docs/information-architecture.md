# Arquitetura de informação - telas e navegação

Este documento mostra como o professor se move pelo frontend do Classroom
Downloader. Ele é a planta baixa da interface: quais telas existem, como elas se
conectam e que papel cada uma cumpre.

Para a arquitetura técnica do sistema, veja [architecture.md](architecture.md). Para
o ciclo de correção com IA, veja [grading-lifecycle.md](grading-lifecycle.md). Para
estilo visual, tokens, CSS e a convivência entre sistemas de UI, a referência é
`apps/web/FRONTEND.md`.

O frontend é uma SPA em React + Vite. Hoje não existem rotas de URL para cada tela;
a navegação é controlada por um único estado, `view`, em `apps/web/src/App.tsx`. Os
valores possíveis ficam no tipo `AppView`, em `types.ts`.

---

## 1. As duas molduras da interface

A interface usa duas molduras principais, dependendo do momento do usuário.

### Login em tela cheia

Quando `view` é `connect`, o app mostra apenas a `LoginScreen`. Não há barra lateral
nem moldura do app. Essa é a porta de entrada e também a tela para onde o usuário
volta quando precisa reconectar o Google.

Isso não é raro: como o OAuth fica em modo Testing, o token do Google expira a cada
7 dias. A consequência está detalhada em [constraints.md](constraints.md#sete-dias).

### App com barra lateral

Em qualquer outra tela, o app usa o casco principal: barra lateral (`Rail`) à
esquerda e conteúdo à direita.

Depois que o usuário conecta a conta, a transição normal é sair de `connect` e entrar
em `workspace`.

---

## 2. A barra lateral (`Rail`)

A barra lateral é a navegação principal do app. Ela mistura atalhos de tela com
informações de conexão.

### Área de trabalho

| Item | Vai para | Observação |
| --- | --- | --- |
| Admin | `admin` | Só aparece para administradores |
| Corrigir com IA | `graderQueue` | Fica desabilitado sem conexão |
| Turmas | `workspace` | Tela inicial depois do login |
| Histórico | `history` | Mostra exportações locais |

### Conectado

Esse bloco não é navegação. Ele mostra o estado dos escopos de Google Classroom e
Google Drive, como `ok` ou `necessário`. A barra também concentra logout e troca de
tema: claro, escuro ou sistema.

---

## 3. Os dois fluxos principais

Depois do login, o app gira em torno de dois caminhos: exportar arquivos e corrigir
com IA. Os dois começam em **Turmas**.

### 3.1. Exportação de arquivos

```text
workspace -> progress -> done -> history
```

- **`workspace`** (`TurmasView`) - o professor escolhe uma turma, vê as atividades,
  pré-visualiza a árvore de pastas no `DryRunDrawer` e inicia a exportação.
- **`progress`** (`ProgressView`) - acompanha a exportação em andamento, com log e
  contagem. `Esc` volta para a área de trabalho.
- **`done`** (`DoneView`) - mostra o resumo do que foi baixado. `Enter` leva ao
  histórico.
- **`history`** (`HistoryView`) - lista o histórico local de exportações, salvo no
  navegador.

### 3.2. Correção com IA

```text
graderQueue -> graderSetup -> graderReview -> graderWrap
```

- **`graderQueue`** (`GraderQueue`) - lista os trabalhos de correção, incluindo a
  seção de arquivados. Dali o professor prepara um novo job ou abre um existente.
- **`graderSetup`** (`GraderSetup`) - etapa de preparo: critérios, inferência de
  rubrica e auditoria de privacidade. Ao continuar, o app dispara o rascunho.
- **`graderReview`** (`GraderReview`) - revisão entrega por entrega. Como o rascunho
  chega por streaming, o professor pode começar a revisar enquanto o restante ainda
  está sendo gerado.
- **`graderWrap`** (`GraderWrap`) - fechamento do job: exportação do resultado,
  limpeza de cache e acesso ao painel flutuante de lançamento, o PiP.

Esse fluxo também pode começar em **Turmas**. Uma atividade pode ser enviada para a
fila, ou seguir direto para preparo ou revisão. Quando o professor abre um job
existente, o destino depende do estado dele; os estados estão descritos em
[grading-lifecycle.md](grading-lifecycle.md).

### O PiP de lançamento

O painel de lançamento fica em `grader/pip/PostingPiP.tsx` e usa `useDocumentPiP`.
Ele abre uma janela flutuante de Document Picture-in-Picture, que continua visível
por cima da aba do Google Classroom.

Essa janela mostra os dados da entrega, atalhos de copiar/colar e deep-links para o
Classroom. É assim que o app ajuda o professor a lançar notas **manualmente**. O app
não publica nada sozinho; o motivo está em [constraints.md](constraints.md).

---

## 4. Admin

- **`admin`** (`AdminView`) - tela visível apenas para administradores. Ela reúne
  eventos da aplicação, estatísticas e tentativas de chamada ao modelo, incluindo
  custo, status e payload. É a tela de observabilidade ligada às rotas de admin em
  [api.md](api.md).

---

## 5. Estados de erro

Erros aparecem como uma camada transversal, não como um único destino de navegação.
A classificação fica em `lib/errorCatalog.ts`, separada por tier, e os componentes
ficam em `components/errors/`.

| Camada | Quando aparece |
| --- | --- |
| **Gate** | Erro bloqueante de tela cheia, como consentimento parcial do Google ou necessidade de reconectar. Substitui o conteúdo. |
| **InlineError** | Erro recuperável dentro da tela, com ação para tentar de novo. |
| **OfflinePill** | Selo discreto quando a API está fora do ar. |
| **Banner de versão** | Frontend e backend estão em versões diferentes (`version_skew`); oferece recarregar. |
| **GradingHealthBanner** | Correção por IA indisponível, por falta de chave do provedor ou modelo não habilitado no catálogo. |
| **ErrorBoundary / FullError** | Captura falhas inesperadas de renderização e mostra uma tela cheia de erro. |

---

## 6. Mapa rápido: `view` -> componente

| `view` | Componente | Fluxo |
| --- | --- | --- |
| `connect` | `LoginScreen` | Entrada / login |
| `workspace` | `TurmasView` | Exportação |
| `progress` | `ProgressView` | Exportação |
| `done` | `DoneView` | Exportação |
| `history` | `HistoryView` | Exportação |
| `graderQueue` | `GraderQueue` | Correção |
| `graderSetup` | `GraderSetup` | Correção |
| `graderReview` | `GraderReview` | Correção |
| `graderWrap` | `GraderWrap` + `PostingPiP` | Correção |
| `admin` | `AdminView` | Observabilidade |

O estado por trás dessas telas fica principalmente nos hooks `useConnection`,
`useExportWorkspace`, `useGradingQueue` e `useGradingJob`. As chamadas HTTP ficam no
cliente `lib/api.ts`.
