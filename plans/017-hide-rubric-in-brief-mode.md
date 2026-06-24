# Plan 017 — Hide the rubric on the review screen for "Orientação simples" (brief mode)

> Source: Notion TODO "No caso de orientação simples, não deve ser exibido rubrica
> na tela de revisão de grading, pois rubricas não são utilizadas em orientações
> simples."
> Theme: **C — Grading review screen**. Priority P2. Effort S (frontend-only).
> Depends on: none. Can land any time.
> Base: branch off `main` @ `6d6b264`.

## Why
"Orientação simples" is `rubric_mode: "brief"` (`GraderSetup.tsx:19` —
`{ id: "brief", title: "Orientação simples", … }`). In brief mode the teacher
pastes a short free-text grading note (`rubric_text`); no weighted criteria are
used. But the review screen **always** renders the criteria breakdown
(`GraderReview.tsx:332-349`): it shows either the "A IA vai sugerir os critérios…"
pending hint or the per-criterion `weight%` rows. For brief mode those rows are the
unused default criteria — noise that misrepresents how the grade was produced.

## Files
- `apps/web/src/components/grader/GraderReview.tsx` — the breakdown block at
  lines 332-349.

## Steps
1. In `GraderReview`, gate the entire breakdown / criteria-pending block on the
   rubric mode. Render it only when criteria are meaningful — i.e. **not** brief
   mode:
   ```ts
   const usesRubric = job.rubric_mode !== "brief";
   ```
   When `!usesRubric`, render neither the `criteria-pending` hint nor the
   `breakdown` list.
2. For brief mode, if `job.rubric_text` is present, optionally show it as a small
   read-only "Orientação" note in that slot so the teacher sees what guided the
   draft (the brief was the actual instruction). Keep it lightweight — a single
   muted block, not a rubric. If the design reference has no such element, omit it
   and just leave the space empty.
3. Leave `teacher_loop: "off"` behavior alone — that path already has no AI score;
   it is out of scope here. Only `rubric_mode` drives this change.

## Notes / guardrails
- Do **not** change the data model or the engine — criteria still exist server-side
  (the default rows); this is purely a display gate.
- Confirm the wrap screen (`GraderWrap.tsx`) and CSV export don't depend on the
  review breakdown being rendered — they don't (they read scores/feedback), so no
  change needed there.
- This plan and Plan 018 (per-criterion progress bars) touch the **same breakdown
  block**. If both are scheduled, do **018 first** (it restructures the block to
  show per-criterion scores) and fold this brief-mode gate into 018's new
  structure, or do 017 first as the trivial gate and let 018 build on it. Either
  order works; just don't write the gate twice.

## Acceptance
- Build/test/lint green.
- Manual/mock: a brief-mode job's review screen shows no weighted-criteria rows;
  an infer/structured job still shows them unchanged.
- e2e green.
