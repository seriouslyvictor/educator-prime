# Arquitetura - Classroom Downloader

Este documento explica, em linguagem direta, como o Classroom Downloader se organiza.
A ideia é que uma pessoa, ou outro agente, consiga entender em poucos minutos como
as peças principais se conectam antes de abrir o código.

Para os limites do produto, privacidade e restrições impostas pelo Google, leia
[constraints.md](constraints.md). Este arquivo fica focado na arquitetura.

---

## 1. O que é

O Classroom Downloader ajuda professores a trabalhar com entregas do Google
Classroom. Hoje ele faz duas coisas principais:

1. **Exporta entregas** para uma pasta local organizada no computador do professor.
2. **Rascunha correções com IA**, sempre como material de apoio. O professor revisa,
   ajusta e decide o que usar.

A ferramenta não publica notas nem comentários de volta no Classroom. Isso não é uma
decisão cosmética: é uma restrição real da API do Google, detalhada em
[constraints.md](constraints.md).

Também vale reforçar o contexto de uso: este não é um produto público. É uma
ferramenta interna, multiusuário, rodando em um VPS, usada pelo autor e por colegas.

---

## 2. As duas partes do sistema

O repositório é um monorepo com dois aplicativos:

| Pasta | Papel | Stack |
| --- | --- | --- |
| `apps/api` | Backend, API e integrações | Python, FastAPI, SQLModel, SQLite |
| `apps/web` | Frontend, interface do professor | TypeScript, React 19, Vite |

Em desenvolvimento, os dois rodam separados. O Vite usa a porta 5173 e repassa as
chamadas `/api/*` para o FastAPI, que roda na porta 8000.

Em produção, tudo vira **um único container Docker**. O FastAPI serve a API em
`/api/*` e também entrega o frontend já compilado, usando `CD_STATIC_DIR`. Isso
deixa o deploy simples: uma porta, um domínio, um container. O passo a passo de
infra fica em [coolify-deploy.md](coolify-deploy.md).

Essa montagem acontece em `apps/api/.../main.py`: primeiro entram os routers da API;
por último entra uma rota "pega-tudo" que devolve o frontend.

---

## 3. Os interruptores entre mock e mundo real

O app foi desenhado para abrir e funcionar sem Google real e sem IA paga. Assim dá
para testar o fluxo logo depois de clonar o repositório.

Três variáveis de ambiente controlam essa troca. Elas ficam em `apps/api/.env`; a
tabela completa está no `README.md`.

| Variável | `mock` (padrão) | `google` / `litellm` (real) |
| --- | --- | --- |
| `CD_GOOGLE_PROVIDER` | Usa dados locais falsos, com turmas e entregas de exemplo | Usa Google OAuth, Classroom e Drive reais |
| `CD_GRADING_ENGINE` | Gera uma correção determinística falsa | Usa LiteLLM com um modelo de IA real |
| `CD_LLM_MODEL_CATALOG_MODE` | Não se aplica | Controla a busca dinâmica da tabela de preços dos modelos |

No modo `mock`, nada sai para a internet. Esse é o caminho mais seguro para validar
tela, navegação e estados principais sem depender de credenciais.

---

## 4. Como os dados circulam

Os dois fluxos mais importantes começam da mesma forma: o professor escolhe uma
turma e uma atividade.

### Fluxo A - exportação de arquivos

```text
Turma -> Atividade -> POST /api/exports -> backend busca anexos no Drive
      -> frontend grava a árvore de pastas no disco
```

Quem escreve os arquivos na máquina é o navegador, via File System Access API. O
backend intermedia o conteúdo vindo do Drive, mas não escolhe a pasta final nem
grava diretamente no computador do professor.

### Fluxo B - correção com IA

Este é o fluxo mais importante do app. Um trabalho de correção (`GradingJob`) passa
por estados claros:

```text
ready -> drafting -> reviewing -> completed
              (arquivar, ocultar e restaurar são marcações separadas)
```

Na prática, o caminho é este:

1. **Fila e preparo** - o professor cria o job, define os critérios da rubrica e
   vincula os links do Classroom.
2. **Auditoria de privacidade** - antes de qualquer texto ir para a IA, o conteúdo
   é removido de identificadores como nomes e e-mails. Cada aluno vira um
   pseudônimo.
3. **Rascunho** - o conteúdo anonimizado vai para a IA, que devolve nota por
   critério e comentário. O fluxo suporta retomada se cair no meio e também uma
   segunda passada para sinalizar notas destoantes.
4. **Revisão** - o professor confere cada entrega, ajusta o que precisar e aprova.
5. **Conclusão e exportação** - o resultado pode sair em CSV. Depois disso, o
   professor lança manualmente no Classroom, com apoio do painel flutuante (PiP).

As rotas desse fluxo ficam sob `/api/grading/...`. Para ver a lista completa, rode o
backend e abra `/docs`, a documentação interativa do FastAPI.

### As duas pistas de extração

Quando o app precisa ler o conteúdo de uma entrega, ele segue uma de duas pistas:

- **Pista de visão** - imagens e PDFs vão para um modelo multimodal, que consegue
  analisar pixels, manuscritos, diagramas e layout.
- **Pista de texto** - arquivos Office (`.docx`, `.xlsx`, `.pptx`) passam por
  extração textual. Texto é lido; elementos visuais desenhados dentro do arquivo
  podem se perder.

Essa diferença importa bastante. Um Canvas de modelo de negócio desenhado em um
Word, por exemplo, pode perder o sentido quando vira apenas texto. O mesmo material
em PDF ou imagem tende a funcionar melhor. A limitação está explicada em
[constraints.md](constraints.md#office-visual).

---

## 5. Onde os dados ficam guardados

- **Banco**: SQLite. Em produção, banco e caches ficam sob `/data`, em volume
  persistente.
- **Token do Google**: salvo em disco, em `/data/tokens/...`, criptografado em
  repouso.
- **Caches**: fontes usadas na correção e exports possuem cache com TTL configurável
  por `CD_GRADING_CACHE_TTL_HOURS`.

Para privacidade, o relatório de auditoria não guarda texto extraído, texto
raspado, prompts, nomes nem e-mails de alunos. Ele guarda apenas metadados seguros.
Isso é requisito de produto, não detalhe de implementação.

---

## 6. Mapa essencial de pastas

```text
apps/api/src/classroom_downloader/
  main.py            -> monta o app e serve o frontend
  routers/           -> rotas da API: auth, courses, exports, grading, admin, health
  google_provider.py -> integra Google Classroom, Drive e modo mock
  grading/           -> ciclo de vida da correção: fila, critérios, rascunho, revisão
  litellm_engine.py  -> chamada ao modelo de IA e mitigação de mojibake
  privacy*.py        -> raspagem de PII e auditoria
  *_extraction.py    -> leitura de zip, Office e conteúdo das entregas
  models.py          -> tabelas do banco

apps/web/src/
  components/        -> telas: workspace, grader, admin, errors, login, PiP
  hooks/             -> estado e chamadas para a API
  lib/api.ts         -> cliente da API
```

Para entender as telas e a navegação do frontend, o melhor ponto de partida hoje é
`apps/web/FRONTEND.md`. Ele documenta os dois sistemas de UI que ainda convivem no
projeto. Um mapa dedicado de navegação ainda não existe e pode ser um bom próximo
documento.

---

## 7. Como rodar e como subir

- **Desenvolvimento**: siga o `README.md`. O backend usa `uv`, o frontend usa
  `pnpm`, e o modo `mock` é o padrão.
- **Produção**: use o container Docker único no Coolify. As instruções estão em
  [coolify-deploy.md](coolify-deploy.md).
