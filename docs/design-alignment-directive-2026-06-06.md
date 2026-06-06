# Directive — Align Classroom Grader with the high-fidelity design

> Execution directive for the implementing agent. Source of truth for the design is
> `docs/UI Design - Final/` (read the grader JSX/CSS before touching code). The downloader-era
> design under `docs/UI Design/` is superseded.

## Context / why

The AI-grading flow has drifted from the approved hi-fi design. Fix four things:

1. **Userflow (biggest offense).** The privacy audit currently runs behind a full-screen modal
   (`GradingProgressModal`) instead of *inline* on the same Setup screen where the teacher picks the
   work mode. The design (`grader/setup.jsx`) folds the audit into Setup as phases:
   `config → running (inline) → prepared (gate before drafting)`.
2. **Rubric inference happens too late.** Backend infers criteria during the *draft* phase (after
   audit). The teacher must see the proposed rubric **before** deciding whether to let AI grade — so
   inference runs on entering Setup, ahead of the audit, and the editable proposed rubric shows in
   the Infer panel.
3. **Grade screen isn't streamed; privacy badge is overbuilt.** Stream each student's draft as it
   arrives (skeletons for the not-yet-done), keep a persistent audit strip, and show a compact
   `PrivacyBlock` — **just status icon + short description; drop the `pb-foot` "Leitura/IA" chips.**
4. **Turmas + tokens.** "Turmas" gets the full `Tela de Atividades` makeover; primary token moves
   green `#059669` → indigo `#2a2fe0` app-wide (AI accent stays purple `#6b3fe0`).

### Locked decisions
- Auto-infer rubric on entering Setup (real backend call, streamed inline).
- **Real per-student SSE.** Students not yet graded show **skeleton placeholders** so the teacher
  sees how many remain; the **rail count badge and topbar counts update live** as drafts arrive.
- Full new Turmas layout (not a restyle).
- Indigo primary + purple AI **app-wide** (connect/history/downloader included).

### CSS mechanism (important)
`apps/web/vite.config.ts` sets `css.modules.generateScopedName: "[local]"`, so every `*.module.css`
class name is effectively **global**. Components import a module with `void styles` and use plain
string class names. Follow this pattern for all new styles. Existing global grader CSS lives in
`apps/web/src/components/grader/Grader.module.css` (~2300 lines).

---

## 1. Color tokens — `apps/web/src/styles/tokens.css`
- Light: `--primary: #2a2fe0`, `--primary-soft: #e8e8ff`. Dark: `--primary-soft: #2b2c5a`.
  (Values from `docs/UI Design - Final/styles.css:16-17,49`.) Keep `--ai: #6b3fe0`.
- Brand/primary gradient → `linear-gradient(135deg, var(--primary), #6b3fe0)` (design `.brand-mark`).
  Point the existing brand-mark rule (in `Rail.module.css` or grader CSS) at the token.
- `apps/web/src/components/workspace/ClassroomList.tsx:59` palette →
  `["#2A2FE0", "#1F8A5B", "#B8740B", "#6b3fe0", "#c7421e", "#0e7490"]`.

## 2. Icons — `apps/web/src/components/icons.tsx`
Add lucide mappings used by the new panels: `lock` (Lock), `eyeOff` (EyeOff), `star` (Star),
`alertCircle` (AlertCircle), `arrowRight` (ArrowRight), `listChecks` (ListChecks), `book` (BookOpen),
`target` (Target), `send` (Send), `moreHorizontal` (MoreHorizontal), `edit` (Pencil), `paperclip`
(Paperclip), `upload` (Upload). Reuse `chevronRight` flipped (`className="ico flip"`) for "left".

## 3. Backend — infer before audit, stream drafts per student
`apps/api/src/classroom_downloader/main.py` + `grading.py` + `tests/test_grading.py`.

**a. Pre-audit criteria inference (streamed).** Add `GET /api/grading/jobs/{job_id}/criteria/stream`
that runs the existing `maybe_infer_job_criteria` (`main.py:297`, wrapping `infer_job_criteria`
`grading.py:250`) with `on_progress`, emitting `{phase:"criteria", processed,total,current}` events
and a final `{phase:"criteria", done:true, job:<snapshot>}`. It must **not** call
`ensure_privacy_audit_allows_draft` (runs before the audit).
- **Privacy guard:** verify what `infer_job_criteria` feeds the engine. It should use the assignment
  description + structural signal, not raw PII. If it reads submission text, route it through the
  same scrub/redaction path the audit uses so inference stays privacy-safe even though it precedes
  the audit gate.

**b. Remove inference from the draft path** to avoid re-running it: drop the
`maybe_infer_job_criteria` calls in `draft_job` (`main.py:1118`) and `stream_draft_job`
(`main.py:1159`). Keep `infer_job_criteria`'s idempotent guard as a safety net.

**c. Per-student draft streaming.** Add an `on_submission` callback to `draft_grading_job`
(`grading.py:402`), invoked after each `_draft_submission` (loop `:436-449`) with that submission's
serialized snapshot (reuse the per-submission read model used by `grading_job_snapshot`). In
`stream_draft_job` (`main.py:1132`) emit `{phase:"draft", processed,total, submission:<snapshot>}`
per student plus the final `{phase:"draft", done:true, job:<snapshot>}`.

**Tests:** extend `tests/test_grading.py` for the new criteria-stream endpoint and assert the draft
stream emits incremental `submission` events.

## 4. App.tsx — rewire flow, no audit modal
`apps/web/src/App.tsx`.
- **Retire `GradingProgressModal`** as the audit/criteria surface (delete component + its render at
  `App.tsx:924`). Audit + inference progress render inside `GraderSetup`; draft progress inside
  `GraderReview`.
- **Setup auto-infers.** In `gradeActivity`/`openGradingJob` ready path: create job → go to
  `graderSetup` → for `infer` mode immediately open the criteria stream; feed progress into Setup
  state and set `gradingJob` (with inferred criteria) on done.
- **Audit inline.** `runGradingPrivacyAudit`/`startGradingAuditForItem` keep using
  `privacyAuditStreamUrl`, but progress flows into `GraderSetup` props (no modal); on completion set
  `privacyAudit` → prepared gate.
- **Draft streaming.** `continueToGradingDraft`: navigate to `graderReview` immediately, then consume
  the enhanced draft stream, applying each `submission` event into `gradingJob.submissions`
  incrementally; derive "not yet drafted" (e.g. `ai_score == null && !error`) for skeletons. Final
  `done` swaps in the full job. Counts (rail badge + topbar) update live off `job.submissions`.

## 5. GraderSetup.tsx — inline audit + real inferred rubric
`apps/web/src/components/grader/GraderSetup.tsx` (+ `Grader.module.css`).
- Phases `config | inferring | auditing | prepared`. `inferring`: small "Definindo critérios…"
  panel. `auditing`: replace the rubric panel with inline `AuditRunningPanel` (port `setup.jsx:186`).
- **Infer panel shows real criteria** from `gradingJob.criteria` (toggle + editable weights), per
  `InferPanel` (`setup.jsx:20`). Other modes keep behavior, adopt design copy/markup.
- Primary CTA `Auditar e preparar {n}` runs the audit inline (no modal); footer keeps `audit-gate-hint`.
- Prepared gate: keep `PreparedPanel`, align to design — stats `Aprovadas / Redigidas / Retidas /
  Alto risco`, reassurance "Nomes e e-mails foram ocultados…", details table, `Gerar N rascunhos e
  revisar` disabled on high-risk.
- Context card roster row → `Nomes e e-mails dos alunos · ocultados` with `eyeOff` icon.

## 6. GraderReview.tsx — streamed grading, trimmed privacy badge
`apps/web/src/components/grader/GraderReview.tsx` (+ `Grader.module.css`).
- **Persistent `AuditStrip`** under the topbar (port `grade.jsx:14`) + "Ver relatório" →
  `AuditReport` drawer (port `grade.jsx:35`, reuse `audit-table`). Counts from `privacyAudit`/job.
- **Stream strip + skeletons.** While drafting show `stream-strip` (`grade.jsx:541`) with
  `drafted/total`; not-yet-drafted rows render a **skeleton** state (shimmer score, "gerando
  rascunho…") via new `.student-row.drafting`/`.skeleton` styles; active not-yet-drafted student shows
  `aside-drafting` spinner (`grade.jsx:298`).
- **Replace `privacy-status-grid` with `PrivacyBlock`** (port `grade.jsx:256`) but **omit the
  `pb-foot` chips** — render only: icon + "Privacidade" label + status tag + one-line description
  (+ optional `pb-flags`). Map from `submission.privacy_status`/`extraction_status`.

## 7. Turmas — full `Tela de Atividades`
New `apps/web/src/components/workspace/TurmasView.tsx` + `Turmas.module.css` (port
`docs/UI Design - Final/grader/library.css`, recolored to tokens). Replace the two-pane `workspace`
render in `App.tsx:793`.
- Left **class sidebar** (real `courses`, active = `selectedCourseId`, token palette) + header
  ("{course} · {n} atividades · selecione para enviar à fila").
- Activities **grouped by state** from `gradingByActivity`: `A corrigir` (no job/ready) · `Em revisão`
  (drafting|reviewing) · `Concluídas` (completed|posted). Row = checkbox + title + meta + per-state
  primary action (`Corrigir com IA`/`Retomar`/`Revisar`/`Ver notas`; AI action gets purple sparkle) +
  `⋯` overflow (Prévia, Baixar entregas, Reclassificar, Abrir no Classroom). Wire to existing
  `onGrade`/`onRegrade`/`onPreview`/`onDownload`.
- **Bulk select → `BulkBar`** ("Enviar N para a fila") navigates to `graderQueue`. Keep
  `GradingHealthBanner` and the dry-run drawer wiring.

## Critical files
- `apps/web/src/styles/tokens.css`, `components/icons.tsx`
- `apps/web/src/App.tsx`; `components/grader/{GraderSetup,GraderReview}.tsx`, `Grader.module.css`;
  delete `components/grader/GradingProgressModal.tsx`
- `apps/web/src/components/workspace/TurmasView.tsx` (new), `Turmas.module.css` (new),
  `ClassroomList.tsx`
- `apps/api/src/classroom_downloader/main.py`, `grading.py`, `tests/test_grading.py`
- Reference only: `docs/UI Design - Final/grader/{setup,grade,queue,library}.jsx`,
  `grader/styles.css`, `grader/library.css`, `styles.css`

## Verification
1. **Backend:** `cd apps/api && uv run --extra dev pytest tests/test_grading.py`.
2. **Run:** API `uv run --extra dev python -m uvicorn classroom_downloader.main:app --app-dir src --reload --port 8000`;
   web `cd apps/web && pnpm run dev` (mock provider).
3. **Walk the flow:** Turmas (grouped, indigo, bulk) → "Corrigir com IA" → Setup **auto-infers**
   rubric (editable) before audit → "Auditar e preparar" runs **inline** (running → prepared) →
   "Gerar rascunhos" → Review **streams** students with skeletons, rail/topbar counts climbing, audit
   strip + report drawer, `PrivacyBlock` showing only status icon + description → Post.
4. **Build:** `cd apps/web && pnpm run build`.
5. Confirm indigo primary across connect/history/downloader and the brand gradient.

---

## Implementation Progress

- [x] Backend criteria inference stream added at `GET /api/grading/jobs/{job_id}/criteria/stream`.
  - Verified by targeted red/green test slice:
    `uv run --extra dev pytest tests/test_grading.py -k "criteria_stream_infers_before_audit or draft_no_longer_infers_criteria_inline or draft_stream_emits_incremental_submissions_without_criteria_phase"`.
- [x] Draft endpoints no longer run criteria inference inline.
- [x] Draft SSE now emits per-submission `submission` payloads before the terminal job snapshot.
- [x] App-wide primary token moved to indigo `#2a2fe0`; AI accent remains `#6b3fe0`.
- [x] Required lucide icon mappings added.
- [x] `GradingProgressModal` retired from the flow and deleted; criteria, audit, and draft progress render inline.
- [x] Setup now opens/creates a ready job, auto-runs criteria streaming for infer mode, shows real inferred criteria, and runs privacy audit only from the inline CTA.
- [x] Review now navigates immediately for draft streaming, patches per-submission SSE payloads into the job, shows skeleton/drafting states, persistent audit strip, report drawer, and a trimmed `PrivacyBlock` without `pb-foot` chips.
- [x] Turmas view replaced the old two-pane workspace with the grouped `Tela de Atividades` layout, class sidebar, overflow actions, and bulk queue bar.
- [x] Frontend build verified after the flow/UI rewrite: `pnpm run build`.
