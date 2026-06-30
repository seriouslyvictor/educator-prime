# Educator Prime (assistente de correções)

O Educator Prime ajuda professores a trabalhar com entregas do Google Classroom:
baixar e organizar arquivos, preparar correções com apoio de IA, revisar resultados
e manter o professor no controle do lançamento final.

O projeto nasceu como **Classroom Downloader**, focado em exportação local de
entregas. Hoje ele é mais amplo: um assistente de correção para turmas que usam
Google Classroom, ainda em formato de ferramenta interna/MVP funcional.

O público principal são professores individuais e cursos pequenos que precisam
ganhar tempo sem transformar a correção em uma caixa-preta. A IA pode ser usada de
forma mais cautelosa, como rascunho revisado entrega por entrega, ou de forma mais
automatizada. Em todos os casos, quem escolhe o grau de automação e assume o
resultado é o professor.

## O que ele faz hoje

- Conecta ao Google Classroom e ao Google Drive.
- Lista turmas, atividades e entregas.
- Exporta arquivos de uma atividade para uma estrutura local organizada.
- Cria trabalhos de correção com critérios/rubricas.
- Faz auditoria de privacidade antes de enviar conteúdo textual para IA.
- Usa IA para gerar notas por critério e comentários, com revisão humana.
- Permite retentativas, revisão de casos individuais e marcação de outliers.
- Prepara uma saída estruturada para revisão, registro e lançamento manual.
- Ajuda o professor a navegar até as entregas no Classroom durante o lançamento.

Um fluxo típico fica assim:

1. O professor conecta a conta Google.
2. Escolhe turma, atividade e escopo da correção.
3. Define ou infere critérios de avaliação.
4. Roda a auditoria de privacidade.
5. Gera as correções com o nível de automação escolhido.
6. Revisa notas, comentários e casos sinalizados.
7. Usa o resultado revisado para registrar e lançar as notas manualmente.

## O que ele não faz

- Não substitui o julgamento do professor.
- Não publica notas ou comentários automaticamente no Google Classroom.
- Não transforma a API do Google em algo que ela não permite. Há limites reais de
  OAuth, escopos, modo Testing e expiração de token.
- Não garante privacidade visual total em imagens. Esse ponto é importante:
  imagens, prints, fotos e arquivos com conteúdo visual podem carregar rostos,
  nomes, documentos ou outros dados sensíveis que a trilha textual não consegue
  censurar com segurança hoje.
- Não é uma plataforma pública pronta para qualquer escola usar sem configuração.
  O app depende de credenciais Google, usuários autorizados e decisões cuidadosas
  de implantação.

Há uma direção de produto para pré-processar imagens e censurar dados sensíveis com
Google Sensitive Data Protection ou serviço parecido. Isso ainda não é uma garantia
atual do sistema.

## Privacidade

Privacidade é requisito central do produto, principalmente porque o sistema lida
com dados de estudantes e, muitas vezes, menores de idade.

Antes da correção com IA, o app roda uma auditoria de privacidade. O fluxo usa
pseudônimos, metadados seguros e etapas de bloqueio ou alerta para reduzir o risco
de enviar informação sensível ao modelo. O objetivo não é só "usar IA", mas criar
um caminho em que o professor consiga inspecionar o que será processado.

Alguns cuidados são deliberados:

- relatórios de auditoria não guardam texto extraído bruto;
- nomes e e-mails de estudantes não são persistidos em relatórios de IA;
- conteúdos de alto risco podem ser bloqueados antes da etapa de correção;
- a correção por IA continua subordinada à revisão e decisão do professor;
- arquivos com imagem exigem cuidado extra, porque ainda não há censura visual
  confiável antes da extração.

Para os limites completos, leia [docs/constraints.md](docs/constraints.md).

## Como funciona

O produto gira em torno de dois fluxos principais.

**Exportação de arquivos:** o professor escolhe uma turma e uma atividade, o backend
busca os anexos pelo Classroom/Drive, e o frontend grava os arquivos no computador
do usuário usando a File System Access API do Chromium.

**Correção assistida:** o professor cria um job de correção, define critérios,
vincula links do Classroom, roda a auditoria de privacidade e então gera correções
com IA ou com o motor mock de desenvolvimento. O resultado passa por revisão,
retentativas e sinalização de outliers antes de virar material de lançamento.

Por dentro, o projeto usa:

- Frontend: Vite, React, TypeScript e componentes locais no estilo shadcn.
- Backend: FastAPI, SQLModel e SQLite.
- Google: OAuth, Classroom API e Drive API.
- IA: motor mock para desenvolvimento ou LiteLLM com modelo configurável.
- Armazenamento local: banco SQLite, tokens criptografados, caches de exportação e
  cache temporário de arquivos usados na correção.

## Rodando localmente

O backend roda em modo mock por padrão. Assim dá para abrir o produto e testar os
fluxos principais sem credenciais reais do Google e sem chamadas pagas de IA.

Backend:

```powershell
cd apps/api
uv run --extra dev python -m uvicorn classroom_downloader.main:app --app-dir src --reload --port 8000
```

Frontend:

```powershell
cd apps/web
pnpm install
pnpm run dev
```

Abra `http://127.0.0.1:5173`.

Mantenha o backend ligado enquanto usa o frontend. O Vite encaminha chamadas
`/api/*` para `http://127.0.0.1:8000`; se a API estiver desligada, o navegador vai
mostrar uma falha genérica de proxy.

Para configuração local, copie `apps/api/.env.example` para `apps/api/.env` e ajuste
apenas o que for necessário.

## Configurações principais

| Variável | Valores comuns | Uso |
| --- | --- | --- |
| `CD_GOOGLE_PROVIDER` | `mock`, `google` | Escolhe dados falsos locais ou Google OAuth/Classroom/Drive reais. |
| `CD_GRADING_ENGINE` | `mock`, `litellm` | Usa corretor determinístico local ou chamadas reais via LiteLLM. |
| `CD_LITELLM_MODEL` | id do modelo | Modelo usado pelo LiteLLM quando a IA real está ligada. |
| `CD_DATABASE_URL` | URL SQLite | Caminho do banco local ou persistente em produção. |
| `CD_SESSION_SECRET_KEY` | segredo longo | Criptografa tokens OAuth salvos em disco. Obrigatório com Google real. |
| `CD_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Controla a verbosidade dos logs do backend. |
| `CD_GRADING_CACHE_PATH` | caminho local | Cache temporário dos arquivos usados na correção. |

Para usar Google real, `CD_GOOGLE_PROVIDER=google` exige client ID, client secret,
redirect URI e chave de sessão. Para usar IA real, `CD_GRADING_ENGINE=litellm`
também exige a chave do provedor do modelo escolhido, como `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY` ou `GEMINI_API_KEY`.

## Docker e Coolify

O `Dockerfile` da raiz compila o frontend Vite e serve tudo pelo backend FastAPI na
porta `8000`. Em produção, o app pode rodar em um único domínio.

Para Coolify, a implantação esperada usa o fluxo de aplicação por repositório Git,
build pack Dockerfile, porta exposta `8000` e volume persistente em `/data`. Esse
volume guarda banco SQLite, tokens OAuth e caches.

O guia completo fica em [docs/coolify-deploy.md](docs/coolify-deploy.md).

## Documentação recomendada

- [docs/index.md](docs/index.md) - entrada da documentação.
- [docs/architecture.md](docs/architecture.md) - visão geral do sistema e dos
  fluxos principais.
- [docs/constraints.md](docs/constraints.md) - limites do produto, privacidade,
  Google OAuth, escopos e decisões de segurança.
- [docs/grading-lifecycle.md](docs/grading-lifecycle.md) - ciclo de vida de um job
  de correção.
- [docs/information-architecture.md](docs/information-architecture.md) - telas,
  navegação e estados do frontend.
- [docs/api.md](docs/api.md) - referência das rotas.
- [docs/decisions.md](docs/decisions.md) - decisões fechadas e histórico técnico.
- [docs/coolify-deploy.md](docs/coolify-deploy.md) - implantação em produção.
