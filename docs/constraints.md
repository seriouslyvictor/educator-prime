# Restrições - o que a ferramenta faz, o que não faz, e por quê

Este é o documento mais importante para entender os limites do Classroom
Downloader. Ele registra as regras que não aparecem só olhando o código: decisões de
produto, restrições da API do Google, custos de distribuição e limitações dos
modelos de IA.

Antes de prometer uma melhoria, mudar um fluxo de permissão ou mexer no caminho de
correção, leia este arquivo. Para a visão de como as peças se encaixam, veja
[architecture.md](architecture.md).

---

## 1. O que a ferramenta faz hoje

Hoje o app:

- **Exporta** entregas do Google Classroom para uma pasta local organizada.
- **Rascunha correções com IA**, com nota por critério e comentário, sempre para
  revisão do professor.
- **Audita privacidade** antes da IA: anonimiza o aluno com pseudônimo e remove
  identificadores do texto.
- **Bloqueia ou sinaliza** entregas não suportadas, incompletas ou arriscadas antes
  de elas entrarem no fluxo de correção.

O ponto central é simples: o app prepara trabalho para o professor, mas não substitui
a decisão dele.

---

## 2. O que a ferramenta não faz

### Não lança nota nem comentário no Classroom

O app não publica nota nem feedback de volta no Google Classroom. Isso não é uma
trava temporária nem um excesso de cautela; são limites da própria API.

1. `studentSubmissions.patch` só funciona em atividades criadas pelo próprio projeto
   OAuth do app. Se a atividade foi criada pelo professor na interface do Classroom,
   a API retorna **403 PERMISSION_DENIED**. Esse comportamento continuava valendo em
   2025.
2. Não existe API para escrever comentário particular ou feedback textual. A API só
   permite mexer em `draftGrade` e `assignedGrade`.

Na prática, lançamento automático só seria possível se o app também criasse as
atividades. Esse não é o caso real de uso: professores já criam atividades no
Classroom. Por isso o caminho escolhido é um assistente com humano no comando. O app
rascunha, organiza, exporta e ajuda no copiar/colar com o painel flutuante (PiP),
mas quem publica é o professor.

Uma alternativa com bookmarklet ou automação de DOM dentro de `classroom.google.com`
foi considerada e descartada em 2026-06-06. O DOM do Google é ofuscado e muda com
frequência; o custo de manutenção seria alto demais para o ganho.

### Não enxerga conteúdo visual dentro de arquivos Office {#office-visual}

A extração de conteúdo tem duas pistas:

- **Visão**: imagens e PDFs vão para o modelo como conteúdo multimodal.
- **Texto**: arquivos `.docx`, `.xlsx` e `.pptx` passam por extração textual.

A diferença parece pequena, mas muda muito o resultado. Quando um aluno desenha algo
dentro de um arquivo Office, como caixas, formas, SmartArt ou diagramas, esse
conteúdo cai na pista de texto. O arquivo não necessariamente dá erro; ele apenas
perde a estrutura visual.

Exemplos comuns:

- Um Business Model Canvas feito no Word pode perder caixas, imagens e relação entre
  quadrantes.
- Organogramas e diagramas em Word ficam quase invisíveis para a extração.
- Um PPTX pode entregar os rótulos, mas perder hierarquia, setas e conectores.

Se o mesmo material for enviado como imagem ou PDF, ele segue pela pista de visão e
tem muito mais chance de ser compreendido. Converter Office para PDF antes da IA
exigiria LibreOffice headless no caminho geral, o que foi evitado de propósito por
complexidade e custo operacional. Então esta é uma limitação conhecida, não um bug
simples de corrigir.

---

## 3. Privacidade é requisito de produto {#privacidade}

Privacidade não é uma camada opcional neste projeto. É parte do contrato do produto:

- Antes de qualquer texto ir para a IA, nomes e e-mails são raspados, e cada aluno
  recebe um pseudônimo.
- O relatório de auditoria não guarda texto extraído, texto raspado, prompts, nomes
  de alunos nem e-mails. Ele guarda apenas metadados seguros.
- A correção por IA é sempre rascunho. Nada é postado de volta no Classroom.

Quem mexer no caminho de extração, auditoria ou correção precisa preservar essas
garantias. Esse tipo de quebra pode passar despercebido em testes superficiais.

---

## 4. O problema de distribuição: o escopo do Google prende o app em Testing

Este é o limite estrutural mais importante do projeto.

O app precisa de escopos OAuth do Google, definidos em
`apps/web/src/hooks/useConnection.ts`. Os escopos de Classroom são de leitura e não
são o maior problema. O ponto crítico é este:

```text
https://www.googleapis.com/auth/drive.readonly
```

Esse escopo é classificado pelo Google como **restricted**, ou seja, de alto risco.
Ao mesmo tempo, ele é necessário para o produto funcionar. A API do Classroom retorna
os IDs dos anexos, mas o conteúdo real vem pelo Drive, via `files().get_media` ou
`export_media`. Tanto o download quanto a correção por IA dependem desse caminho.

As saídas normais foram analisadas e não resolvem o problema:

| Saída | Por que não funciona aqui |
| --- | --- |
| **Internal**, dentro do Workspace da escola | O autor leciona no **SENAI**, uma rede estadual grande. Aprovar um projeto GCP pela organização exigiria uma iniciativa institucional, não uma ferramenta de alguns professores. |
| **External + In production**, aberto ao público | Como `drive.readonly` é restricted, o Google exige verificação com avaliação de segurança CASA. O custo e a burocracia não cabem no tamanho do projeto. |
| **Trocar por um escopo de Drive mais estreito** | Não há um escopo mais estreito que permita ler os anexos das entregas do Classroom. |

Decisão tomada em junho de 2026: manter o OAuth em **Testing** e projetar o app em
volta das consequências disso. Não reproponha tipo de usuário `Internal`, corte de
escopo ou Drive sob demanda; isso já foi analisado.

---

## 5. A restrição dos 7 dias {#sete-dias}

O modo Testing traz dois custos concretos:

1. **O token expira a cada 7 dias.** O refresh token do Google deixa de valer depois
   de uma semana. Cada colega precisa refazer o login e passar pelas telas de
   consentimento periodicamente. Por isso a tela de login e re-login é parte central
   do produto, não um caso raro.
2. **O limite é de 100 usuários de teste.** Cada pessoa precisa ser adicionada
   manualmente no Google Cloud Console. Não existe auto-cadastro.

A avaliação do autor é pragmática: algumas telas de login por semana podem valer a
pena se economizarem horas de correção. Mas a interface precisa tratar esse re-login
com clareza, sem fingir que a sessão será permanente.

---

## 6. Consentimento é tudo de uma vez

Já foi tentado pedir permissões gradualmente, liberando escopos conforme a ação do
usuário. Essa abordagem foi revertida e está fechada desde o plano 013.

O motivo foi prático: o login ficou instável e o fluxo virou uma sequência de telas
de permissão a cada poucas ações. Como o app só tem utilidade dentro do ecossistema
Classroom/Drive, a regra atual é pedir todo o conjunto de escopos no login.

Não proponha consentimento incremental, `capability gating` ou Drive sob demanda
para este projeto.

---

## 7. Limitação do modelo de IA: mojibake {#mojibake}

Há um bug conhecido do lado do Google/Gemini: em algumas respostas, inclusive usando
`gemini-2.5-flash` via LiteLLM, o texto volta com charset corrompido. Acentos podem
aparecer como lixo, por exemplo `código` virando uma sequência quebrada ou
`Inicialização` voltando ilegível.

O problema é intermitente e acontece por requisição. O mesmo prompt pode voltar
correto em uma chamada e corrompido na próxima. Em dados reais de junho de 2026,
apareceu em cerca de 1 a cada 12 entregas. Nosso prompt sai em ASCII, então a origem
da corrupção não está no texto enviado pelo app.

Isso já causou dois efeitos ruins: feedback difícil de ler e barras de nota vazias,
porque o pareamento dos critérios dependia do nome do critério, e um nome corrompido
não batia com a rubrica local.

A mitigação atual tem três camadas, em `litellm_engine.py` e `grading/drafting.py`:

1. **Prevenir** - o prompt pede JSON somente ASCII, com escapes `\uXXXX`. O
   `json.loads` recupera os acentos corretamente depois.
2. **Detectar e repetir** - se a maioria dos critérios retornados não bate com a
   rubrica, a chamada é considerada corrompida e refeita até 2 vezes. Se persistir,
   o app usa o melhor resultado e registra log.
3. **Tolerar** - as notas são associadas aos critérios por posição, não por nome. Os
   rótulos exibidos na UI vêm da rubrica local, então continuam legíveis.

Se for mexer no motor de correção, preserve essas três camadas.

---

## 8. Resumo rápido

- A correção é **rascunho**. O app não posta nota nem feedback no Classroom.
- `drive.readonly` é obrigatório e restricted, então o app fica em OAuth
  **Testing**.
- Testing significa **re-login a cada 7 dias** e **até 100 usuários de teste**
  adicionados manualmente.
- O consentimento é pedido **todo de uma vez**. O fluxo incremental foi descartado.
- Conteúdo visual dentro de Office se perde porque segue pela pista de texto.
- Gemini pode corromper acentos em algumas respostas; há mitigações, mas não uma
  solução definitiva na origem.
- Privacidade é requisito: nada de guardar texto, prompts, nomes ou e-mails de
  alunos; tudo deve ser anonimizado antes da IA.
