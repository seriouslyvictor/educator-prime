# Graph Report - Classroom Downloader  (2026-06-11)

## Corpus Check
- 114 files · ~151,755 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1349 nodes · 3488 edges · 68 communities (62 shown, 6 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 387 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1dae6996`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Grading Domain & DB Models|Grading Domain & DB Models]]
- [[_COMMUNITY_Persistence & API Dependencies|Persistence & API Dependencies]]
- [[_COMMUNITY_Grading Tests & Settings|Grading Tests & Settings]]
- [[_COMMUNITY_Grading Router & Job Snapshots|Grading Router & Job Snapshots]]
- [[_COMMUNITY_LiteLLM Grading Engine|LiteLLM Grading Engine]]
- [[_COMMUNITY_LLM Catalog & Settings|LLM Catalog & Settings]]
- [[_COMMUNITY_Google Classroom Provider|Google Classroom Provider]]
- [[_COMMUNITY_LLM Model Overrides Config|LLM Model Overrides Config]]
- [[_COMMUNITY_Schemas & Privacy Audit|Schemas & Privacy Audit]]
- [[_COMMUNITY_Auth Flow & Token Store|Auth Flow & Token Store]]
- [[_COMMUNITY_Workspace Views (UI)|Workspace Views (UI)]]
- [[_COMMUNITY_App Shell & Flow Views (UI)|App Shell & Flow Views (UI)]]
- [[_COMMUNITY_Frontend API Client & Export|Frontend API Client & Export]]
- [[_COMMUNITY_Grader Review UI|Grader Review UI]]
- [[_COMMUNITY_Router Split Design (Docs)|Router Split Design (Docs)]]
- [[_COMMUNITY_UI Primitives & Grader Setup|UI Primitives & Grader Setup]]
- [[_COMMUNITY_Submission & Drive Hydration|Submission & Drive Hydration]]
- [[_COMMUNITY_Web Package Dependencies|Web Package Dependencies]]
- [[_COMMUNITY_Exports Router & File Naming|Exports Router & File Naming]]
- [[_COMMUNITY_TypeScript Config|TypeScript Config]]
- [[_COMMUNITY_Privacy Redaction (PII)|Privacy Redaction (PII)]]
- [[_COMMUNITY_Provider Sessions & Cache Logging|Provider Sessions & Cache Logging]]
- [[_COMMUNITY_Observability & Logging|Observability & Logging]]
- [[_COMMUNITY_Grader Shell (UI)|Grader Shell (UI)]]
- [[_COMMUNITY_Navigation Rail & Theme|Navigation Rail & Theme]]
- [[_COMMUNITY_Grading Resume Tests|Grading Resume Tests]]
- [[_COMMUNITY_Courses Router|Courses Router]]
- [[_COMMUNITY_Filesystem API Types|Filesystem API Types]]
- [[_COMMUNITY_Project README|Project README]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]

## God Nodes (most connected - your core abstractions)
1. `log_event()` - 99 edges
2. `get_settings()` - 97 edges
3. `GradingJob` - 33 edges
4. `GradingSubmission` - 33 edges
5. `GoogleProvider` - 32 edges
6. `scrub_submission_cached()` - 32 edges
7. `GradingStatus` - 32 edges
8. `safe_fields()` - 30 edges
9. `_CapturingEngine` - 29 edges
10. `log_warning()` - 28 edges

## Surprising Connections (you probably didn't know these)
- `Graph Signature: main.py Across Six Communities` --references--> `Project Knowledge Graph (graphify-out)`  [INFERRED]
  plan.md → CLAUDE.md
- `UserSession` --uses--> `AuthFailure`  [INFERRED]
  apps/api/src/classroom_downloader/api/session_cleanup.py → apps/api/src/classroom_downloader/api/auth_errors.py
- `AuthFailure` --uses--> `AuthFailure`  [INFERRED]
  apps/api/src/classroom_downloader/api/session_cleanup.py → apps/api/src/classroom_downloader/api/auth_errors.py
- `ExtractedSubmissionContent` --uses--> `GradingFileCache`  [INFERRED]
  apps/api/src/classroom_downloader/content_extraction.py → apps/api/src/classroom_downloader/models.py
- `GradingCriterionInput` --uses--> `ExtractedSubmissionContent`  [INFERRED]
  apps/api/src/classroom_downloader/grading/criteria.py → apps/api/src/classroom_downloader/content_extraction.py

## Import Cycles
- 1-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/main.py`
- 1-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/api/deps.py`
- 1-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/api/common.py`
- 1-file cycle: `apps/api/src/classroom_downloader/google_provider.py -> apps/api/src/classroom_downloader/google_provider.py`
- 1-file cycle: `apps/api/src/classroom_downloader/grading/_common.py -> apps/api/src/classroom_downloader/grading/_common.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/deps.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/health.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/main.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/api/deps.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/api/deps.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/api/deps.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/api/deps.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/api/auth_errors.py`

## Hyperedges (group relationships)
- **api/ Support Layer (common, auth_errors, session_cleanup, deps)** — plan_api_common, plan_api_auth_errors, plan_api_session_cleanup, plan_api_deps [EXTRACTED 0.90]
- **Domain Routers by Bounded Context** — plan_routers_health, plan_routers_auth, plan_routers_courses, plan_routers_exports, plan_routers_grading [EXTRACTED 0.90]
- **One-Way Import Chain (main to routers to deps to api-support to services)** — plan_compat_reexports, plan_routers_grading, plan_api_deps, plan_api_session_cleanup, plan_api_auth_errors [EXTRACTED 0.85]

## Communities (68 total, 6 thin omitted)

### Community 0 - "Grading Domain & DB Models"
Cohesion: 0.11
Nodes (38): GradingFileCache, GradingAiAttempt, GradingEngine, GradingJob, GradingSubmission, Session, datetime, ExtractedSubmissionContent (+30 more)

### Community 1 - "Persistence & API Dependencies"
Cohesion: 0.10
Nodes (38): AuthFailure, _contains_invalid_grant(), google_auth_http_exception(), _http_403_is_hard_auth_failure(), _http_error_content(), Google auth-error → HTTP translation.  Pure, no side effects., _as_utc(), get_current_session() (+30 more)

### Community 2 - "Grading Tests & Settings"
Cohesion: 0.08
Nodes (39): get_settings(), test_brief_mode_sends_rubric_text_and_keeps_default_criteria(), test_classroom_links_endpoint_backfills_links_and_posted_state(), test_create_job_persists_teacher_criteria(), test_defaults_used_when_no_criteria_and_engine_silent(), test_delete_cache_preserves_results_and_marks_metadata(), test_draft_auto_runs_privacy_audit_when_missing(), test_draft_blocks_when_latest_audit_has_high_risk_rows() (+31 more)

### Community 3 - "Grading Router & Job Snapshots"
Cohesion: 0.08
Nodes (63): _conditional_response(), _etag(), _if_none_match(), _sse_event(), Build the grading engine, translating config failures (missing key /     disabl, resolve_grading_engine(), Request, Response (+55 more)

### Community 4 - "LiteLLM Grading Engine"
Cohesion: 0.06
Nodes (75): Path, Any, GradingEngineRequest, LlmModelEntry, VisionExtractionResult, Path, GradingEngineRequest, LlmModelEntry (+67 more)

### Community 5 - "LLM Catalog & Settings"
Cohesion: 0.14
Nodes (34): Any, Path, Settings, Path, Settings, BaseSettings, _bool_or_none(), _cache_is_stale() (+26 more)

### Community 6 - "Google Classroom Provider"
Cohesion: 0.14
Nodes (12): ClassroomActivity, ClassroomCourse, FakeClassroomService, FakeCourses, FakeCourseWork, FakeDriveFiles, FakeDriveService, FakeExecute (+4 more)

### Community 7 - "LLM Model Overrides Config"
Cohesion: 0.05
Nodes (38): display_name, enabled, notes, rpm_limit, tpm_limit, use_cases, default_model, display_name (+30 more)

### Community 8 - "Schemas & Privacy Audit"
Cohesion: 0.31
Nodes (21): BaseModel, ExportStatus, GradingStatus, ActivityRead, AuthStart, AuthState, CourseRead, ExportCreate (+13 more)

### Community 9 - "Auth Flow & Token Store"
Cohesion: 0.15
Nodes (32): GradingCriterion, Session, GradingAiAttempt, GradingSubmission, GradingSubmissionFile, Session, Path, ExportError (+24 more)

### Community 10 - "Workspace Views (UI)"
Cohesion: 0.13
Nodes (17): EmptyState(), SearchBox(), SkeletonRows(), GraderQueue(), ReferenceQueueCard(), referenceQueueStatus(), GraderWrap(), Course (+9 more)

### Community 11 - "App Shell & Flow Views (UI)"
Cohesion: 0.07
Nodes (25): ConnectView(), InlineError(), DoneView(), HistoryView(), AppIcon(), IconName, icons, ProgressLogItem (+17 more)

### Community 12 - "Frontend API Client & Export"
Cohesion: 0.09
Nodes (27): DryRunDrawer(), api, CacheEntry, cacheKey(), CacheOptions, fetchJson(), inFlight, request() (+19 more)

### Community 13 - "Grader Review UI"
Cohesion: 0.10
Nodes (24): BlockedEvidence(), extensionOf(), GraderReview(), hasDefaultCriteria(), initials(), INLINE_IMAGE_MIME, INLINE_TEXT_EXTENSIONS, INLINE_TEXT_MIME (+16 more)

### Community 14 - "Router Split Design (Docs)"
Cohesion: 0.10
Nodes (28): Graphify Codebase-Query Workflow, Project Knowledge Graph (graphify-out), api/auth_errors.py (auth-error to HTTP translation), api/common.py (SSE + HTTP-cache primitives), api/deps.py (FastAPI dependencies), api/session_cleanup.py (session + cache purge), App-Owned Aggregate Tier (GradingJob + children), Bounded Contexts (auth, classroom-read, exports, grading) (+20 more)

### Community 15 - "UI Primitives & Grader Setup"
Cohesion: 0.16
Nodes (16): Card(), CardContent(), CardDescription(), CardFooter(), CardHeader(), CardTitle(), cn(), RadioGroup() (+8 more)

### Community 16 - "Submission & Drive Hydration"
Cohesion: 0.16
Nodes (7): clear_google_provider_caches(), MockGoogleProvider, TokenStore, log_event(), safe_fields(), Shared pytest configuration for the API test suite.  Two isolation concerns ar, _reset_global_state()

### Community 17 - "Web Package Dependencies"
Cohesion: 0.10
Nodes (19): dependencies, lucide-react, react, react-dom, vite, @vitejs/plugin-react, devDependencies, @types/react (+11 more)

### Community 18 - "Exports Router & File Naming"
Cohesion: 0.31
Nodes (13): GoogleProvider, Request, Response, Session, ExportCreate, ExportFile, ExportJobRead, _build_export_read() (+5 more)

### Community 19 - "TypeScript Config"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+10 more)

### Community 20 - "Privacy Redaction (PII)"
Cohesion: 0.18
Nodes (17): is_valid_cpf(), Validate a Brazilian CPF by its two mod-11 check digits., Unit tests for the pt-BR privacy scrubber (`classroom_downloader.privacy`).  The, _scrub(), test_clean_text_has_no_counts(), test_combined_redactions_report_all_categories(), test_email_redacted(), test_full_name_redacted_lone_first_name_preserved() (+9 more)

### Community 21 - "Provider Sessions & Cache Logging"
Cohesion: 0.12
Nodes (25): datetime, AccountProfile, _cache_hit(), drive_files_from_submission(), _due_label(), get_google_provider(), GoogleApiProvider, _looks_like_user_id() (+17 more)

### Community 22 - "Observability & Logging"
Cohesion: 0.25
Nodes (11): Any, _bounded_repr(), _bounded_text(), _format_event(), _format_value(), JsonEventFormatter, log_warning(), _safe_value() (+3 more)

### Community 23 - "Grader Shell (UI)"
Cohesion: 0.28
Nodes (4): GraderTopbar(), postingClipboardText(), scoreOf(), GradingJob

### Community 24 - "Navigation Rail & Theme"
Cohesion: 0.07
Nodes (26): 0. Goal & context, 1. Guiding principle — split by layer, preserve the DAG, 2. Target package layout, 3. Exact move map (symbol → destination), 4. Import/test coupling — the real risk, 5.1 The `get_grading_engine` patch point — #1 trap, 5.2 `litellm` patch point — already safe, just expose it, 5.3 Circular imports (+18 more)

### Community 25 - "Grading Resume Tests"
Cohesion: 0.39
Nodes (6): _create_job(), Coverage for the resume/preview additions: the global grading-jobs list and the, test_jobs_list_collapses_to_newest_per_activity(), test_jobs_list_surfaces_created_job(), test_submission_preview_forces_download_for_unsafe_type(), test_submission_preview_streams_image_inline()

### Community 26 - "Courses Router"
Cohesion: 0.21
Nodes (13): Activity, _as_utc(), _cache_headers(), _is_fresh(), _is_future(), SSE + generic HTTP-cache primitives.  No domain dependencies., datetime, GoogleProvider (+5 more)

### Community 27 - "Filesystem API Types"
Cohesion: 0.40
Nodes (4): FileSystemDirectoryHandle, FileSystemFileHandle, FileSystemWritableFileStream, Window

### Community 32 - "Community 32"
Cohesion: 0.15
Nodes (16): Request, Response, Session, AuthStart, AuthState, build_oauth_authorization_url(), DbTokenStore, Loads and refreshes Google credentials stored in the UserSession DB row. (+8 more)

### Community 33 - "Community 33"
Cohesion: 0.07
Nodes (27): API Design, Backend Design, Bottom Line, Capture object in the engine, Cleanup, Current Findings, Existing persistence, Existing type gap (+19 more)

### Community 34 - "Community 34"
Cohesion: 0.15
Nodes (16): _ensure_activity_columns(), _ensure_cache_columns(), _ensure_columns(), _ensure_grading_ai_attempt_columns(), _ensure_grading_criterion_columns(), _ensure_grading_job_columns(), _ensure_grading_submission_columns(), _ensure_privacy_columns() (+8 more)

### Community 35 - "Community 35"
Cohesion: 0.22
Nodes (23): ExtractedSubmissionContent, GoogleProvider, GradingEngine, GradingFileCache, GradingJob, GradingSubmission, Session, SubmissionFile (+15 more)

### Community 36 - "Community 36"
Cohesion: 0.08
Nodes (24): 0. Goal & context, 10. Known accepted limitations (document, don't fix), 1. Files touched (overview), 2.1 Where extraction happens — draft time, never audit time, 2.2 The vision extraction call (draft path), 2.3 Multi-attachment submissions, 2.4 Attempt recording & cost, 2. Pipeline design (+16 more)

### Community 37 - "Community 37"
Cohesion: 0.09
Nodes (21): Architecture summary, Execution Directive: LiteLLM grading — intervention levels, batch mode & cost observability, Final verification, Guardrails (every task), Implementation status — updated 2026-06-05, PHASE 1 — Make the teacher-intervention spectrum real, PHASE 2 — Structured output + prompt caching, PHASE 3 — Cost, token & time observability (+13 more)

### Community 38 - "Community 38"
Cohesion: 0.09
Nodes (21): 0. Goal & context, 1. Guiding principle — ownership tiers (DO NOT "fix" these), 2. Target package layout, 3. Exact move map (symbol → destination), 4. Test coupling — preserve or repoint (the real risk), 5. Watch-items (gotchas that will bite), 6. Phased execution with verification gates, 7. Explicitly out of scope (+13 more)

### Community 39 - "Community 39"
Cohesion: 0.10
Nodes (20): 1. Context & motivation, 2.1 `models.py` — extend `GradingSubmission` (after `error`, ~line 134), 2.2 `database.py` — dev migration for the new columns, 2.3 `google_provider.py` — read-only links lookup, 2.4 `main.py` — two thin endpoints (mirror existing grading endpoints), 2.5 `schemas.py` — extend `GradingSubmissionRead` (line 130), 2.6 `grading.py` — map fields in `_submission_read` (line 1198), 2. Backend changes (`apps/api/src/classroom_downloader/`) (+12 more)

### Community 40 - "Community 40"
Cohesion: 0.11
Nodes (17): 0. Implementation ledger, 10. Phased delivery, 11. Risks & tradeoffs, 12. Open questions (need your call), 1. Assessment of what exists today, 2. LiteLLM capabilities to lean on (from current docs), 3. Wire the teacher-intervention spectrum (the core ask), 4. Two execution modes via env: `per_submission` vs `class_batch` (+9 more)

### Community 41 - "Community 41"
Cohesion: 0.12
Nodes (15): Implementation Plan: Logging & cache observability, Phase 0 — Safety net & conventions (no behavior change), Phase 1 — Formatter: make plain output operable (high value, low risk), Phase 2 — Redact PII and bound object dumps (highest-priority correctness), Phase 3 — Uniform cache hit/miss instrumentation (the core ask), Phase 4 — Hit-rate summaries & DEBUG tier (readability), Phase 5 — Request correlation (optional, nice-to-have), Phase 6 — Verify & commit (+7 more)

### Community 42 - "Community 42"
Cohesion: 0.13
Nodes (14): AI Grading Layer, Attempt Metadata, Current State, Engine Selection, Extraction Support, LiteLLM Engine, Logging, Model Catalog (+6 more)

### Community 43 - "Community 43"
Cohesion: 0.13
Nodes (14): 1. Color tokens — `apps/web/src/styles/tokens.css`, 2. Icons — `apps/web/src/components/icons.tsx`, 3. Backend — infer before audit, stream drafts per student, 4. App.tsx — rewire flow, no audit modal, 5. GraderSetup.tsx — inline audit + real inferred rubric, 6. GraderReview.tsx — streamed grading, trimmed privacy badge, 7. Turmas — full `Tela de Atividades`, Context / why (+6 more)

### Community 44 - "Community 44"
Cohesion: 0.13
Nodes (14): Current state (findings), Goal, Implementation Plan: Decompose the frontend into co-located CSS-Module components, Phase 0 — Safety net, Phase 1 — Establish the global layer, Phase 2 — Split the component files (prerequisite for co-location), Phase 3 — Co-locate CSS as Modules, one component at a time, Phase 4 — Delete the husk (+6 more)

### Community 45 - "Community 45"
Cohesion: 0.50
Nodes (4): Path, serve_static_frontend(), _static_frontend_root(), FileResponse

### Community 46 - "Community 46"
Cohesion: 0.15
Nodes (12): Caching Strategy, Cross-Cutting Requirements, Current Hotspots, Decision Summary, Implementation Progress, Privacy Audit: Efficiency Evaluation, Recommended Sequencing, Tier 1 — Privacy audit and scrub memoization (hottest path) (+4 more)

### Community 47 - "Community 47"
Cohesion: 0.20
Nodes (9): Out of scope, Papercut ironing plan — IA grading draft, Task 1 — Separate privacy flags from grading flags ✅ DONE, Task 2 — Honor the selected rubric mode ✅ DONE, Task 3 — Make inferred criteria editable ✅ DONE, Task 4 — One student = one multi-file submission ✅ DONE (leaner variant), Task 5 — Honest, predictable draft queue ✅ DONE, Task 6 — Student-name resolution fallback ✅ DONE (+1 more)

### Community 48 - "Community 48"
Cohesion: 0.36
Nodes (7): checkpoint(), dump_buttons(), first_visible(), rail_nav(), UI blocker audit for Classroom Downloader (mock backend).  Drives the real app f, Rail workspace nav buttons in order: 0=graderQueue, 1=workspace, 2=history., run_flow()

### Community 49 - "Community 49"
Cohesion: 0.25
Nodes (7): Blockers (P0 — primary flow CTAs unreachable at 768px-tall screens), Detector noise to ignore in findings.json, Medium, Not found (worth knowing), Root cause (explains the "unreachable buttons" complaint), Side findings (code, not UI), UI blocker audit — findings draft (2026-06-10)

### Community 50 - "Community 50"
Cohesion: 0.33
Nodes (5): Coolify application setup, Coolify deployment, Google OAuth setup, Required environment variables, Smoke checks after deploy

### Community 51 - "Community 51"
Cohesion: 0.33
Nodes (5): Backend Settings, Classroom Downloader, Development, Docker / Coolify deployment, Stack

### Community 58 - "Community 58"
Cohesion: 0.08
Nodes (24): 0. Goal & context, 10. Watch-items (gotchas that will bite), 1. Files touched (overview), 2. Sentry (backend), 3.1 Structured extras (no console change), 3.2 Request/user context (contextvars), 3.3 The DB sink, 3.4 Retention (+16 more)

### Community 59 - "Community 59"
Cohesion: 0.16
Nodes (21): GoogleProvider, GradingCriterion, GradingEngine, GradingJob, Session, _collect_inference_samples(), infer_job_criteria(), Reuse the audit's cached + scrubbed content to build a privacy-safe sample. (+13 more)

### Community 60 - "Community 60"
Cohesion: 0.37
Nodes (18): GoogleProvider, GradingJob, GradingSubmission, PrivacyAuditRead, Session, SubmissionFile, GoogleProvider, SubmissionFile (+10 more)

### Community 61 - "Community 61"
Cohesion: 0.33
Nodes (18): ExtractedSubmissionContent, GradingJob, GradingSubmission, Session, ExtractedSubmissionContent, GradingJob, GradingPseudonym, GradingSubmission (+10 more)

### Community 62 - "Community 62"
Cohesion: 0.26
Nodes (14): GradingJob, GradingSubmission, GradingSubmissionFile, Session, SubmissionFile, ensure_submission_file(), _group_files(), group_key_for() (+6 more)

### Community 63 - "Community 63"
Cohesion: 0.29
Nodes (7): _sse_payloads(), test_criteria_stream_infers_before_audit(), test_draft_stream_emits_incremental_submissions_without_criteria_phase(), test_draft_stream_emits_per_submission_progress(), test_draft_stream_seeds_full_queue_in_stable_order(), test_privacy_audit_stream_emits_progress_and_terminal_event(), test_update_criteria_replaces_and_survives_reinference()

### Community 64 - "Community 64"
Cohesion: 0.53
Nodes (4): build_output_path(), sanitize_segment(), test_build_output_path_deduplicates_without_overwrite(), test_sanitize_segment_removes_filesystem_hostile_characters()

### Community 65 - "Community 65"
Cohesion: 0.33
Nodes (6): _enable_litellm_engine(), Point settings at a local single-model catalog with litellm selected.     conft, test_draft_returns_503_when_provider_key_missing(), test_grading_health_ready_when_provider_key_present(), test_grading_health_reports_missing_provider_key(), test_grading_health_reports_model_not_enabled()

### Community 66 - "Community 66"
Cohesion: 0.50
Nodes (4): inspect_grading_readiness(), _probe_valid_key(), Live check via litellm.check_valid_key. Returns (ok, detail); ok is None     wh, Non-raising readiness report for the configured grading engine. Used by     the

### Community 67 - "Community 67"
Cohesion: 0.67
Nodes (3): _seed_preview_cache(), test_preview_binary_still_attachment(), test_preview_code_file_served_inline_as_text_plain()

## Knowledge Gaps
- **369 isolated node(s):** `findings`, `flow_failures`, `schema_version`, `default_model`, `enabled` (+364 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `log_event()` connect `Submission & Drive Hydration` to `Grading Domain & DB Models`, `Community 32`, `Persistence & API Dependencies`, `Community 35`, `LiteLLM Grading Engine`, `LLM Catalog & Settings`, `Grading Router & Job Snapshots`, `Auth Flow & Token Store`, `Exports Router & File Naming`, `Provider Sessions & Cache Logging`, `Observability & Logging`, `Courses Router`, `Community 59`, `Community 60`, `Community 61`, `Community 62`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Grading Tests & Settings` to `Grading Domain & DB Models`, `Persistence & API Dependencies`, `Community 34`, `Community 66`, `LiteLLM Grading Engine`, `LLM Catalog & Settings`, `Community 35`, `Grading Router & Job Snapshots`, `Community 65`, `Auth Flow & Token Store`, `Provider Sessions & Cache Logging`, `Observability & Logging`, `Community 59`, `Community 63`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `GoogleProvider` connect `Community 60` to `Grading Domain & DB Models`, `Persistence & API Dependencies`, `Community 35`, `Grading Router & Job Snapshots`, `Google Classroom Provider`, `Auth Flow & Token Store`, `Submission & Drive Hydration`, `Provider Sessions & Cache Logging`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `GradingJob` (e.g. with `GoogleProvider` and `GradingJob`) actually correct?**
  _`GradingJob` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `GradingSubmission` (e.g. with `GoogleProvider` and `GradingJob`) actually correct?**
  _`GradingSubmission` has 20 INFERRED edges - model-reasoned connections that need verification._
- **What connects `UI blocker audit for Classroom Downloader (mock backend).  Drives the real app f`, `Rail workspace nav buttons in order: 0=graderQueue, 1=workspace, 2=history.`, `Dump console + network activity for the first 15s of app load.` to the rest of the system?**
  _412 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Grading Domain & DB Models` be split into smaller, more focused modules?**
  _Cohesion score 0.10801393728222997 - nodes in this community are weakly interconnected._