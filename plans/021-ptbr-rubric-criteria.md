# Plan 021 — Normalize inferred rubric criteria to pt-BR

> Source: Notion TODO "Normalizar critérios inferidos para pt-br, quase sempre os
> critérios estão vindo em inglês."
> Theme: **D — Grading engine quality**. Priority P2. Effort S–M. Depends on: none.
> Base: branch off `main` @ `6d6b264`.

## Why
Inferred criteria almost always come back in English. The default seed criteria are
literally English (`criteria.py:13-34`: `Understanding / Evidence / Reasoning /
Clarity`), and the inference path takes whatever language the model returns —
`_normalize_inferred_criteria` only trims/validates name+weight, it does not
enforce language (`criteria.py:64-87`). The product is pt-BR throughout (all UI
copy, feedback prompts), so English criterion names read as a bug to teachers.

## Where criteria originate
- **Inference**: `infer_job_criteria` → `grading_engine.infer_rubric(request)`
  (`inference.py:64-147`); the engine's inference prompt lives in
  `litellm_engine.py`. The names/descriptions returned there are the main offender.
- **Fallback defaults**: `DEFAULT_CRITERIA` in `criteria.py` (English) — used when
  inference yields nothing (`inference.py:104, 134` → `_existing()`), and seeded by
  `ensure_default_criteria`.

## Files
- `apps/api/src/classroom_downloader/litellm_engine.py` — the rubric-inference
  prompt (`_build_messages` / inference message builder). Instruct the model
  explicitly to return **criterion names and descriptions in Brazilian Portuguese**,
  regardless of the submission/assignment language.
- `apps/api/src/classroom_downloader/grading/criteria.py` — translate
  `DEFAULT_CRITERIA` to pt-BR (e.g. Compreensão / Evidências / Raciocínio /
  Clareza), **and** update every place that pattern-matches the old English default
  names so the "are these the defaults?" checks keep working (see Guardrail).
- `apps/web/src/components/grader/GraderReview.tsx:17-21` and
  `GraderSetup.tsx:352-356` — both `hasDefaultCriteria` helpers hard-code
  `"Understanding|Evidence|Reasoning|Clarity"` and weights `30|25|30|15`. These
  gate UI behavior ("A IA vai sugerir os critérios…"). If you rename the defaults,
  update these signatures too or they silently break.
- Tests: `test_litellm_engine.py` / `test_grading.py`.

## Guardrail — the default-criteria sentinel is load-bearing
The string `Understanding|Evidence|Reasoning|Clarity` is used as a **sentinel** to
detect "still on default criteria" in at least three places (the two frontend
`hasDefaultCriteria`, and `_criteria_match_defaults` in `criteria.py:55-61`).
Renaming the defaults to pt-BR **must** update all of them atomically, or the
"criteria not yet inferred" UI state and the infer-mode flow will misfire. Grep for
both the names and the weight signature before changing.

## Steps
1. Update the inference prompt to require pt-BR criterion names + descriptions
   (one or two explicit sentences; keep the rest of the schema identical).
2. Translate `DEFAULT_CRITERIA` to pt-BR.
3. Update `_criteria_match_defaults` and **both** frontend `hasDefaultCriteria`
   signatures to the new pt-BR names/weights. Consider exporting the canonical
   default names from one module to kill the duplicated literals (optional but
   recommended — three copies is how this regresses).
4. (Optional, defensive) In `_normalize_inferred_criteria`, leave content alone but
   document that language is enforced at the prompt, not post-hoc — a translation
   pass here would add a model call and is unnecessary if the prompt is obeyed.
5. Verify existing jobs in the DB with English criteria still render (this changes
   future inferences + defaults, not historical rows) — no migration needed.

## Acceptance
- Backend `uv run pytest` green; inference tests assert the prompt requests pt-BR
  and that default seeding uses the pt-BR names.
- Frontend build/test/lint green; the infer-mode "criteria pending" hint still
  appears for a fresh job (sentinel updated) and disappears once real criteria land.
- Manual/mock: a freshly inferred rubric shows Portuguese criterion names.
