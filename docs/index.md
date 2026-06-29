# Documentação — Classroom Downloader

Ponto de partida da documentação do projeto. Comece pela visão geral e desça o nível
de detalhe conforme a necessidade.

## Comece por aqui

- **[architecture.md](architecture.md)** — visão geral do sistema: as duas partes
  (web + api), os modos mock/real, por onde os dados passam e o mapa de pastas. Se
  você só vai ler um documento, leia este.
- **[constraints.md](constraints.md)** — o que a ferramenta faz, o que **não** faz e
  por quê. Limites do Google (escopo restrito, modo Testing, 7 dias), privacidade,
  rascunho-apenas, mojibake do Gemini, conteúdo visual em Office. Leitura obrigatória
  antes de prometer qualquer coisa.

## Aprofundamento

- **[grading-lifecycle.md](grading-lifecycle.md)** — o fluxo de correção em detalhe:
  estados do job, pipeline de rascunho, nota por critério, outliers, retomada.
- **[api.md](api.md)** — referência das rotas da API, agrupada por fluxo, com ponteiro
  para a documentação interativa (`/docs`) e o snapshot OpenAPI versionado.
- **[information-architecture.md](information-architecture.md)** — mapa das telas e da
  navegação do frontend (login, Turmas, Corrigir com IA, Admin, estados de erro).

## Operação e histórico

- **[coolify-deploy.md](coolify-deploy.md)** — passo a passo do deploy em container
  único no Coolify.
- **[decisions.md](decisions.md)** — decisões fechadas (não reabrir) e índice dos
  planos históricos.

## Fora desta pasta

- **`README.md`** (raiz) — instalação, comandos de desenvolvimento e tabela de
  configuração do backend.
- **`apps/web/FRONTEND.md`** — convenções de **estilo** do frontend (os dois sistemas
  de UI, tokens, CSS). Complementa o mapa de telas em
  [information-architecture.md](information-architecture.md).
- **`apps/web/docs/token-bridge-findings.md`** — detalhes da ponte de tokens shadcn.
