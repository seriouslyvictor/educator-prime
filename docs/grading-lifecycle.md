# Ciclo de vida da correção

Este documento acompanha o fluxo mais importante do app: como um trabalho de
correção (`GradingJob`) nasce, passa pela IA e chega ao professor para revisão.

Para a visão geral do sistema, leia [architecture.md](architecture.md). Para os
limites de produto, privacidade e Google Classroom, leia
[constraints.md](constraints.md).

O código desse fluxo fica em `apps/api/src/classroom_downloader/grading/`. As rotas
estão em `routers/grading.py` e aparecem também em [api.md](api.md).

---

## 1. O que é um trabalho de correção

Um `GradingJob` representa a correção de uma atividade de uma turma. Ele concentra o
estado necessário para acompanhar o processo inteiro:

- turma e atividade de origem;
- configuração escolhida na criação, como rubrica, escopo e modo;
- critérios de avaliação;
- entregas dos alunos, com uma `GradingSubmission` por aluno;
- resultados da IA e ajustes feitos pelo professor;
- resumo de custo, em tokens e centavos, quando a IA real é usada.

Cada entrega reúne **todos os anexos de um mesmo aluno** em um único card. A ideia é
corrigir o conjunto da entrega, não cada arquivo isoladamente. O agrupamento usa
`group_key`, e a fila segue uma ordem alfabética estável para deixar a tela de
revisão previsível.

---

## 2. Estados do job

O job tem dois eixos de estado, e eles são independentes.

### Progresso da correção (`status`)

| Estado | Significado |
| --- | --- |
| `ready` | O job foi criado e configurado, mas ainda não foi rascunhado |
| `drafting` | A IA está produzindo os rascunhos |
| `reviewing` | Os rascunhos estão prontos e aguardam revisão do professor |
| `completed` | Todas as entregas foram revisadas |

O caminho normal é:

```text
ready -> drafting -> reviewing -> completed
```

Quando o professor revisa a última entrega pendente, o job passa para `completed`
sozinho.

### Organização da fila (`queue_state`)

`queue_state` pode ser `active`, `archived` ou `hidden`. Esse eixo serve para
organizar a lista sem apagar o trabalho. Arquivar, ocultar e restaurar mexem apenas
nessa marcação; o progresso da correção não muda por causa disso.

---

## 3. Etapas do fluxo

### 3.1. Criar o job

O professor escolhe a turma, a atividade e a configuração inicial. Estes são os
campos que mais mudam o comportamento:

- **Rubrica (`rubric_mode`)** - os critérios podem ser definidos manualmente, com
  peso por critério, ou inferidos a partir da descrição da atividade e de uma amostra
  de entregas. Também existe um modo holístico mais simples, chamado "Orientação
  simples", sem nota por critério.
- **Loop do professor (`teacher_loop`)** - quando está `off`, o app prepara e
  anonimiza tudo, mas não chama a IA. É útil quando o professor quer só organizar,
  preparar ou exportar.
- **Escopo (`grade_scope`)** - `all` corrige todas as entregas; `remaining` corrige
  apenas as que ainda não têm nota no Classroom.
- **Conteúdo visual (`include_visual_submissions`)** - define se entregas que seguem
  pela pista de visão entram no lote. A limitação dos arquivos Office está descrita
  em [constraints.md](constraints.md#office-visual).

### 3.2. Definir ou inferir os critérios

Se o modo escolhido for inferência, o app tenta montar a rubrica antes do rascunho,
em `inference.py`.

A preferência é usar a descrição da atividade, quando ela tem conteúdo suficiente.
Se a descrição não ajuda, o app usa uma amostra aleatória, mas reprodutível, de
entregas já anonimizadas. Essa amostra é semeada pelo id do job.

Se não houver sinal útil, a inferência não bloqueia a correção: o app mantém os
critérios padrão. Em todos os casos, os pesos são normalizados para somar 100.

### 3.3. Vincular os links do Classroom

O job recebe os links das entregas no Classroom. Esses links são usados mais tarde,
quando o professor lança a nota manualmente com apoio do painel flutuante (PiP).

### 3.4. Auditar privacidade

Antes de qualquer texto ir para a IA, roda a auditoria em `privacy*.py`. O conteúdo
é raspado de nomes e e-mails, e cada aluno recebe um pseudônimo (`GradingPseudonym`).

O relatório guarda apenas metadados seguros. Ele não guarda o texto original, o
texto raspado nem os prompts. Essa é uma garantia de produto, detalhada em
[constraints.md](constraints.md#privacidade). O progresso dessa etapa pode ser
acompanhado por streaming via SSE.

### 3.5. Gerar o rascunho (`drafting`)

O rascunho acontece em `drafting.py`. Para cada entrega, seguindo a ordem da fila:

1. **Cache e scrub de cada anexo** - o arquivo é baixado uma vez, guardado em cache
   com TTL e anonimizado. Reexecuções reaproveitam esse cache.
2. **Extração por pista** - imagens e PDFs seguem pela pista de visão, multimodal;
   arquivos Office seguem pela pista de texto. Só conteúdo lido e anonimizado com
   segurança vai para o modelo.
3. **Bloqueio antes da IA** - se nenhum anexo puder ser usado, por formato não
   suportado, falha de extração ou falha de raspagem, a entrega é marcada como
   bloqueada com um motivo seguro. Ela não é enviada ao modelo.
4. **Chamada ao modelo** - os anexos anonimizados do aluno são enviados juntos em
   uma única chamada. A resposta volta com nota por critério e comentário.
5. **Pontuação por critério como fonte da verdade** - os pontos em
   `GradingSubmissionCriterionScore` são salvos como inteiros, limitados a
   `[0, peso]`. A nota final é a soma desses pontos, não o número holístico que o
   modelo às vezes devolve em paralelo.

O pareamento entre pontos e critérios é feito por **posição**, não por nome. Isso
protege o fluxo contra a corrupção intermitente de acentos do Gemini descrita em
[constraints.md](constraints.md).

A fila inteira é materializada e publicada de uma vez. Por isso a tela de revisão
mostra todos os alunos imediatamente, enquanto cada item transita por estados como
`na fila`, `rascunhando` e `pronto`. O progresso também é transmitido por SSE.

### 3.6. Segunda passada: outliers

Depois que todos os rascunhos terminam, pode rodar uma segunda passada opcional,
`review_outliers_for_job`, controlada por configuração.

Essa etapa olha o lote inteiro e sinaliza notas destoantes para o professor revisar
com mais atenção. Ela é registrada como um attempt de estágio `outlier_review` e não
roda duas vezes para o mesmo job.

### 3.7. Revisão pelo professor

Com os rascunhos prontos, o job entra em `reviewing`. O professor confere cada
entrega, ajusta nota e comentário quando necessário, e marca a entrega como
revisada.

Quando o professor edita os pontos por critério, a nota final é recalculada a partir
deles. Assim a regra da fonte única da verdade continua valendo. Também existem
ações para retentar uma entrega específica e para marcar que uma entrega já foi
lançada no Classroom.

### 3.8. Concluir e exportar

Quando todas as entregas estão revisadas, o job vira `completed`. O resultado pode
ser exportado em CSV.

O lançamento no Classroom continua sendo manual. O PiP ajuda o professor a navegar e
copiar os dados, mas o app não publica nota nem feedback por conta própria. O motivo
está explicado em [constraints.md](constraints.md).

---

## 4. Conceitos importantes

- **Retomada barata.** Cada anexo baixado e anonimizado fica em cache, e cada
  chamada à IA vira um `GradingAiAttempt`. Se um rascunho cair no meio, uma nova
  execução reaproveita o que já foi feito em vez de repetir downloads e extrações.
  Para uma única entrega, existe também o caminho de retentativa isolada.
- **Status por entrega.** Além do estado geral do job, cada entrega carrega
  `extraction_status`, `privacy_status`, `flag` e `error`. É assim que o app separa
  entrega corrigida, bloqueada antes da IA, sinalizada como outlier ou com falha.
- **Custo e observabilidade.** No fim, o job consolida tokens de prompt, conclusão,
  cache e custo em centavos a partir dos attempts. Os attempts e seus payloads ficam
  disponíveis nas rotas de admin; veja [api.md](api.md).
- **Limpeza de cache.** O cache dos arquivos-fonte expira pelo TTL configurado em
  `CD_GRADING_CACHE_TTL_HOURS` e também pode ser limpo por rota. Apagar um job
  remove todas as tabelas-filhas associadas.

---

## 5. Mapa do módulo `grading/`

```text
grading/
  lifecycle.py        -> apaga job e tabelas-filhas
  criteria.py         -> normalização e edição de critérios
  inference.py        -> inferência da rubrica antes do rascunho
  submission_scope.py -> filtro de escopo: all ou remaining
  submissions.py      -> agrupamento de anexos por aluno e ordenação da fila
  caching.py          -> cache de download e de conteúdo anonimizado
  drafting.py         -> rascunho: pistas, IA, outliers e retentativa
  attempts.py         -> registro de tentativas de IA, custo e status
  snapshots.py        -> snapshots das entregas para streaming e telas
  export.py           -> exportação CSV
```

