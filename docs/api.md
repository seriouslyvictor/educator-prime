# Referência da API

A API é um FastAPI servido em `/api/*`. Este documento é um mapa em linguagem
direta, agrupado por fluxo. Não substitui a fonte da verdade — ele aponta para ela:

- **Documentação interativa**: rode o backend e abra `http://127.0.0.1:8000/docs`.
  É a referência viva, com cada rota, parâmetro e schema de resposta.
- **Contrato versionado**: `apps/api/openapi.snapshot.json` é o schema OpenAPI
  congelado e versionado no Git. O teste `tests/test_openapi_snapshot.py` falha
  sempre que uma rota ou um modelo muda sem o snapshot ser atualizado, então toda
  mudança de contrato vira um diff revisável (em vez de quebrar o frontend em
  silêncio).

Depois de mudar uma rota ou um modelo de propósito, regenere o snapshot:

```text
cd apps/api
uv run python scripts/export_openapi.py
```

Para entender o que está por trás das rotas de correção, veja
[grading-lifecycle.md](grading-lifecycle.md).

---

## Convenções

- Todas as rotas ficam sob o prefixo `/api`.
- Respostas e modelos são definidos com Pydantic/SQLModel (campos em `schemas.py`).
- Erros seguem um contrato comum (`api/errors.py`): corpo com `detail`, código e
  mensagem. Banco travado responde `503 busy_retry`.
- Algumas rotas usam **streaming (SSE)** para progresso em tempo real — marcadas
  abaixo como `(SSE)`.
- As rotas de admin exigem privilégio de administrador.

---

## Saúde

| Método | Rota | Para quê |
| --- | --- | --- |
| GET | `/api/health` | Verificação simples de que o backend está de pé |

---

## Autenticação (Google OAuth)

Fluxo de login em [constraints.md](constraints.md#sete-dias) (atenção ao limite dos
7 dias do modo Testing).

| Método | Rota | Para quê |
| --- | --- | --- |
| GET | `/api/auth/me` | Estado da sessão: logado ou não, e quais escopos foram concedidos |
| POST | `/api/auth/google/start` | Inicia o fluxo OAuth (devolve a URL de consentimento) |
| GET | `/api/auth/google/callback` | Retorno do Google após o consentimento |
| POST | `/api/auth/google/logout` | Encerra a sessão |

---

## Turmas e atividades

Leitura do Google Classroom (com cache local). No modo `mock`, devolve dados de
exemplo.

| Método | Rota | Para quê |
| --- | --- | --- |
| GET | `/api/courses` | Lista as turmas do professor |
| GET | `/api/courses/{course_id}/activities` | Lista as atividades de uma turma |
| GET | `/api/courses/{course_id}/activities/grade-summary` | Resumo de notas por atividade (carregado sob demanda) |

---

## Exportação (baixar arquivos)

| Método | Rota | Para quê |
| --- | --- | --- |
| POST | `/api/exports` | Cria um job de exportação para uma atividade |
| GET | `/api/exports/{job_id}` | Estado do job de exportação |
| GET | `/api/exports/{job_id}/files/{file_id}/content` | Conteúdo de um arquivo (o frontend grava no disco via File System Access API) |

---

## Correção com IA

O conjunto maior de rotas. O fluxo por trás delas está em
[grading-lifecycle.md](grading-lifecycle.md).

### Engine e fila

| Método | Rota | Para quê |
| --- | --- | --- |
| GET | `/api/grading/health` | Disponibilidade do engine de correção (mock ou LiteLLM) |
| GET | `/api/grading/queue` | A fila de trabalhos |
| GET | `/api/grading/jobs` | Lista de jobs |
| POST | `/api/grading/jobs` | Cria um job de correção |
| GET | `/api/grading/jobs/{job_id}` | Detalhe de um job |
| DELETE | `/api/grading/jobs/{job_id}` | Apaga o job e suas tabelas-filhas |

### Organização da fila

| Método | Rota | Para quê |
| --- | --- | --- |
| POST | `/api/grading/jobs/{job_id}/archive` | Arquiva o job |
| POST | `/api/grading/jobs/{job_id}/hide` | Oculta o job |
| POST | `/api/grading/jobs/{job_id}/restore` | Restaura um job arquivado/oculto |

### Preparo: critérios e links

| Método | Rota | Para quê |
| --- | --- | --- |
| PATCH | `/api/grading/jobs/{job_id}/criteria` | Edita a rubrica (critérios e pesos) |
| GET | `/api/grading/jobs/{job_id}/criteria/stream` | Progresso da inferência da rubrica `(SSE)` |
| POST | `/api/grading/jobs/{job_id}/classroom-links` | Vincula os links das entregas no Classroom |

### Auditoria de privacidade

| Método | Rota | Para quê |
| --- | --- | --- |
| POST | `/api/grading/jobs/{job_id}/privacy-audit` | Roda a auditoria de privacidade |
| GET | `/api/grading/jobs/{job_id}/privacy-audit` | Resultado da auditoria |
| GET | `/api/grading/jobs/{job_id}/privacy-audit/stream` | Progresso da auditoria `(SSE)` |
| GET | `/api/grading/jobs/{job_id}/privacy-audit/export.csv` | Exporta a auditoria em CSV |
| GET | `/api/grading/jobs/{job_id}/privacy-audit/export.json` | Exporta a auditoria em JSON |

### Rascunho e revisão

| Método | Rota | Para quê |
| --- | --- | --- |
| POST | `/api/grading/jobs/{job_id}/draft` | Inicia o rascunho com IA |
| GET | `/api/grading/jobs/{job_id}/draft/stream` | Progresso do rascunho, entrega por entrega `(SSE)` |
| GET | `/api/grading/jobs/{job_id}/submissions/{submission_id}/preview` | Prévia de uma entrega para revisão |
| POST | `/api/grading/jobs/{job_id}/submissions/{submission_id}/review` | Salva a revisão do professor (nota/comentário; recalcula a nota final a partir dos critérios) |
| POST | `/api/grading/jobs/{job_id}/submissions/{submission_id}/retry` | Re-rascunha uma entrega específica |
| POST | `/api/grading/jobs/{job_id}/submissions/{submission_id}/posted` | Marca a entrega como já lançada no Classroom |

### Resultado e cache

| Método | Rota | Para quê |
| --- | --- | --- |
| GET | `/api/grading/jobs/{job_id}/export.csv` | Exporta o resultado da correção em CSV |
| DELETE | `/api/grading/jobs/{job_id}/cache` | Limpa o cache de arquivos-fonte do job |

---

## Admin (observabilidade)

Exige privilégio de administrador. Útil para auditar o que aconteceu sem expor
conteúdo sensível.

| Método | Rota | Para quê |
| --- | --- | --- |
| GET | `/api/admin/events` | Eventos da aplicação (log estruturado) |
| GET | `/api/admin/stats` | Estatísticas agregadas |
| GET | `/api/admin/llm/attempts` | Tentativas de chamada ao modelo (custo, status) |
| GET | `/api/admin/llm/attempts/{attempt_id}/payload` | Payload de uma tentativa específica |

---

## Frontend (rota pega-tudo)

Fora de `/api/*`, o backend serve o frontend já compilado (em produção). Qualquer
caminho que não comece com `api/` cai no `index.html` do app React. Isso permite
rodar tudo em um container só — veja [architecture.md](architecture.md) e
[coolify-deploy.md](coolify-deploy.md).
