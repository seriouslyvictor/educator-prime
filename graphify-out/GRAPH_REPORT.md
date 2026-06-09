# Graph Report - Classroom Downloader  (2026-06-08)

## Corpus Check
- 79 files · ~47,591 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1081 nodes · 4046 edges · 67 communities (56 shown, 11 thin omitted)
- Extraction: 67% EXTRACTED · 33% INFERRED · 0% AMBIGUOUS · INFERRED: 1339 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f20b86e2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Core Grading Pipeline|Core Grading Pipeline]]
- [[_COMMUNITY_API Routes & Job Management|API Routes & Job Management]]
- [[_COMMUNITY_LLM Grading Engine|LLM Grading Engine]]
- [[_COMMUNITY_Privacy Audit System|Privacy Audit System]]
- [[_COMMUNITY_Frontend Navigation UI|Frontend Navigation UI]]
- [[_COMMUNITY_Test Fixtures & Settings|Test Fixtures & Settings]]
- [[_COMMUNITY_LLM Model Catalog|LLM Model Catalog]]
- [[_COMMUNITY_UI Component Library|UI Component Library]]
- [[_COMMUNITY_Grader Review Panel|Grader Review Panel]]
- [[_COMMUNITY_Frontend API & Caching|Frontend API & Caching]]
- [[_COMMUNITY_Google Classroom API|Google Classroom API]]
- [[_COMMUNITY_Google Drive Integration|Google Drive Integration]]
- [[_COMMUNITY_UI History & Icons|UI History & Icons]]
- [[_COMMUNITY_Database & Migrations|Database & Migrations]]
- [[_COMMUNITY_Privacy & PII Protection|Privacy & PII Protection]]
- [[_COMMUNITY_Frontend Dependencies|Frontend Dependencies]]
- [[_COMMUNITY_TypeScript Config|TypeScript Config]]
- [[_COMMUNITY_Logging & Observability|Logging & Observability]]
- [[_COMMUNITY_Google Auth & Profile|Google Auth & Profile]]
- [[_COMMUNITY_Grader Workflow UI|Grader Workflow UI]]
- [[_COMMUNITY_Grading Test Doubles|Grading Test Doubles]]
- [[_COMMUNITY_OAuth Token Management|OAuth Token Management]]
- [[_COMMUNITY_Frontend App State|Frontend App State]]
- [[_COMMUNITY_Content Extraction & Scrub|Content Extraction & Scrub]]
- [[_COMMUNITY_DeepSeek Model Config|DeepSeek Model Config]]
- [[_COMMUNITY_Draft Job Pipeline|Draft Job Pipeline]]
- [[_COMMUNITY_Resume & SSE Tests|Resume & SSE Tests]]
- [[_COMMUNITY_Gemini 2.5 Config|Gemini 2.5 Config]]
- [[_COMMUNITY_Gemini Flash Lite Config|Gemini Flash Lite Config]]
- [[_COMMUNITY_OpenAI GPT-5 Config|OpenAI GPT-5 Config]]
- [[_COMMUNITY_xAI Grok Config|xAI Grok Config]]
- [[_COMMUNITY_Grading Stream Tests|Grading Stream Tests]]
- [[_COMMUNITY_Test Cleanup & Token Store|Test Cleanup & Token Store]]
- [[_COMMUNITY_Submission Caching|Submission Caching]]
- [[_COMMUNITY_Engine Readiness Probe|Engine Readiness Probe]]
- [[_COMMUNITY_Provider Key Health Tests|Provider Key Health Tests]]
- [[_COMMUNITY_App Initialization|App Initialization]]
- [[_COMMUNITY_Google Cache Management|Google Cache Management]]
- [[_COMMUNITY_Drive Grouping Tests|Drive Grouping Tests]]
- [[_COMMUNITY_Browser File System Types|Browser File System Types]]
- [[_COMMUNITY_OAuth Auth URL|OAuth Auth URL]]
- [[_COMMUNITY_Claude Code Settings|Claude Code Settings]]
- [[_COMMUNITY_File Preview Tests|File Preview Tests]]
- [[_COMMUNITY_Job Snapshot|Job Snapshot]]
- [[_COMMUNITY_Submission Preview|Submission Preview]]
- [[_COMMUNITY_Local Settings File|Local Settings File]]
- [[_COMMUNITY_Attempt Status Label|Attempt Status Label]]
- [[_COMMUNITY_Attempt Status Tone|Attempt Status Tone]]
- [[_COMMUNITY_Extraction Status Tone|Extraction Status Tone]]
- [[_COMMUNITY_Status Tone Helper|Status Tone Helper]]
- [[_COMMUNITY_ActionBar Component|ActionBar Component]]
- [[_COMMUNITY_Web Package JSON|Web Package JSON]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]

## God Nodes (most connected - your core abstractions)
1. `log_event()` - 93 edges
2. `get_settings()` - 87 edges
3. `GradingStatus` - 66 edges
4. `GoogleProvider` - 64 edges
5. `GradingJob` - 62 edges
6. `GradingSubmission` - 62 edges
7. `GradingEngine` - 50 edges
8. `GradingFileCache` - 48 edges
9. `ExportStatus` - 46 edges
10. `FastAPI` - 45 edges

## Surprising Connections (you probably didn't know these)
- `README (Classroom Downloader project overview)` --references--> `Manual Classroom Posting (API limitation)`  [INFERRED]
  README.md → apps/web/src/components/grader/GraderWrap.tsx
- `README (Classroom Downloader project overview)` --references--> `Privacy Audit Gate (AI sees no student data until audit passes)`  [EXTRACTED]
  README.md → apps/web/src/components/grader/GraderSetup.tsx
- `MockGoogleProvider` --semantically_similar_to--> `MockGradingEngine`  [INFERRED] [semantically similar]
  apps/api/src/classroom_downloader/google_provider.py → apps/api/src/classroom_downloader/grading_engine.py
- `UserSession` --uses--> `AuthFailure`  [INFERRED]
  apps/api/src/classroom_downloader/api/session_cleanup.py → apps/api/src/classroom_downloader/api/auth_errors.py
- `AuthFailure` --uses--> `AuthFailure`  [INFERRED]
  apps/api/src/classroom_downloader/api/session_cleanup.py → apps/api/src/classroom_downloader/api/auth_errors.py

## Import Cycles
- 1-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/main.py`
- 1-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/api/deps.py`
- 1-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/api/common.py`
- 1-file cycle: `apps/api/src/classroom_downloader/google_provider.py -> apps/api/src/classroom_downloader/google_provider.py`
- 1-file cycle: `apps/api/src/classroom_downloader/grading.py -> apps/api/src/classroom_downloader/grading.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/health.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/deps.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/main.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/api/deps.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/api/deps.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/api/common.py`

## Hyperedges (group relationships)
- **AI Grading Pipeline Flow** — classroom_downloader_grading_draftgradingjob, classroom_downloader_grading_cachesubmissionfile, classroom_downloader_grading_scrubsubmissioncached, classroom_downloader_content_extraction_extractsubmissioncontent, classroom_downloader_privacy_scrubsubmission, classroom_downloader_grading_draftsubmission, classroom_downloader_grading_engine_gradingengine [EXTRACTED 1.00]
- **GoogleProvider Implementations** — classroom_downloader_google_provider_googleprovider, classroom_downloader_google_provider_googleapiprovider, classroom_downloader_google_provider_mockgoogleprovider [EXTRACTED 1.00]
- **Privacy Audit Before Draft Gate** — classroom_downloader_main_ensreprivacyauditallowsdraft, classroom_downloader_privacy_audit_runprivacyaudit, classroom_downloader_privacy_audit_latestprivacyaudit, classroom_downloader_main_draftjob, classroom_downloader_main_streamdraftjob [EXTRACTED 1.00]
- **Privacy Pipeline: Scrub → Pseudonymize → Safe Labels → AI** — concept_privacy_scrub, concept_pseudonymization, concept_privacy_safe_source_label [INFERRED 0.90]
- **SSE Streaming Grading Flow: backend stream → App.streamGradingProgress → GraderReview** — concept_sse_stream, web_gradingstreamflow, grader_graderreview [INFERRED 0.85]
- **Rubric Modes (infer/brief/structured/saved) + Teacher Loop + LiteLLM Engine** — concept_rubric_inference, concept_teacher_loop, concept_llm_catalog [INFERRED 0.80]
- **GraderSetup privacy-gated AI drafting flow** — grader_gradersetup, grader_auditrunningpanel, grader_preparedpanel, concept_privacy_audit_gate, lib_api [INFERRED 0.85]
- **Grading status label/tone helper suite** — graderstatus_privacylabel, graderstatus_extractionlabel, graderstatus_safestatuslabel, graderstatus_privacytone, graderstatus_statustone [EXTRACTED 1.00]
- **Workspace view components sharing Course/Activity/GradingQueueItem data** — workspace_activitylist, workspace_classroomlist, workspace_turmasview [INFERRED 0.85]

## Communities (67 total, 11 thin omitted)

### Community 0 - "Core Grading Pipeline"
Cohesion: 0.11
Nodes (100): GradingFileCache, datetime, ExtractedSubmissionContent, GoogleProvider, GradingEngine, GradingFileCache, GradingJob, GradingJobRead (+92 more)

### Community 1 - "API Routes & Job Management"
Cohesion: 0.20
Nodes (76): Activity, Path, Request, Response, Session, AuthStart, AuthState, BaseModel (+68 more)

### Community 2 - "LLM Grading Engine"
Cohesion: 0.20
Nodes (18): Any, GradingEngineRequest, LlmModelEntry, GradingEngineResult, _bounded_number(), _build_messages(), _build_rubric_messages(), build_sample_xml() (+10 more)

### Community 3 - "Privacy Audit System"
Cohesion: 0.12
Nodes (27): AuthFailure, _contains_invalid_grant(), google_auth_http_exception(), _http_403_is_hard_auth_failure(), _http_error_content(), Google auth-error → HTTP translation.  Pure, no side effects., _as_utc(), get_current_session() (+19 more)

### Community 4 - "Frontend Navigation UI"
Cohesion: 0.06
Nodes (29): ConnectView(), InlineError(), DoneView(), DryRunDrawer(), HistoryView(), AppIcon(), IconName, icons (+21 more)

### Community 5 - "Test Fixtures & Settings"
Cohesion: 0.08
Nodes (38): get_settings(), Multi-file Submission Grouping, _CapturingEngine (grading test double), _enable_litellm_engine helper, _seed_infer_job helper, _seed_preview_cache helper, test_brief_mode_sends_rubric_text_and_keeps_default_criteria(), test_classroom_links_endpoint_backfills_links_and_posted_state() (+30 more)

### Community 6 - "LLM Model Catalog"
Cohesion: 0.19
Nodes (21): Any, Path, Settings, BaseSettings, _bool_or_none(), _cache_is_stale(), estimate_cost_cents(), _fetch_upstream() (+13 more)

### Community 7 - "UI Component Library"
Cohesion: 0.09
Nodes (29): Card(), CardContent(), CardDescription(), CardFooter(), CardHeader(), CardTitle(), cn(), RadioGroup() (+21 more)

### Community 8 - "Grader Review Panel"
Cohesion: 0.08
Nodes (27): Teacher-Loop Modes (off/approve/auto/cowrite), BlockedEvidence, BlockedEvidence(), extensionOf(), GraderReview(), hasDefaultCriteria(), initials(), INLINE_IMAGE_MIME (+19 more)

### Community 9 - "Frontend API & Caching"
Cohesion: 0.09
Nodes (28): getInitials(), Rail(), ThemeToggle(), Stale-While-Revalidate API Cache Pattern, AuditStat, PreparedPanel, privacyTone, CacheEntry (+20 more)

### Community 10 - "Google Classroom API"
Cohesion: 0.09
Nodes (19): ClassroomActivity, _due_label(), get_google_provider(), GoogleApiProvider, FakeClassroomService (test double), FakeCourses (test double), FakeDriveService (test double), FakeClassroomService (+11 more)

### Community 11 - "Google Drive Integration"
Cohesion: 0.16
Nodes (7): ClassroomCourse, drive_files_from_submission(), _looks_like_user_id(), A bare numeric Google account id leaking in as a display name (e.g. when a, safe_fields(), test_drive_files_carry_classroom_submission_id_for_grouping(), test_looks_like_user_id_only_flags_bare_numeric_ids()

### Community 12 - "UI History & Icons"
Cohesion: 0.12
Nodes (20): AppIcon, EmptyState(), SearchBox(), SkeletonRows(), ReferenceQueueCard(), referenceQueueStatus(), referenceQueueStatus, Activity (+12 more)

### Community 13 - "Database & Migrations"
Cohesion: 0.15
Nodes (16): _ensure_activity_columns(), _ensure_cache_columns(), _ensure_columns(), _ensure_grading_ai_attempt_columns(), _ensure_grading_criterion_columns(), _ensure_grading_job_columns(), _ensure_grading_submission_columns(), _ensure_privacy_columns() (+8 more)

### Community 14 - "Privacy & PII Protection"
Cohesion: 0.13
Nodes (22): is_valid_cpf(), Validate a Brazilian CPF by its two mod-11 check digits., Safe Source Label (no PII in filenames), Privacy Scrub Pipeline (pt-BR), Student Pseudonymization before AI, AuditStrip / AuditReport, PrivacyBlock, Unit tests for the pt-BR privacy scrubber (`classroom_downloader.privacy`).  The (+14 more)

### Community 15 - "Frontend Dependencies"
Cohesion: 0.10
Nodes (19): dependencies, lucide-react, react, react-dom, vite, @vitejs/plugin-react, devDependencies, @types/react (+11 more)

### Community 16 - "TypeScript Config"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+10 more)

### Community 17 - "Logging & Observability"
Cohesion: 0.20
Nodes (13): Any, _bounded_repr(), _bounded_text(), configure_logging(), _format_event(), _format_value(), JsonEventFormatter, log_error() (+5 more)

### Community 18 - "Google Auth & Profile"
Cohesion: 0.09
Nodes (21): 0. Goal & context, 1. Guiding principle — ownership tiers (DO NOT "fix" these), 2. Target package layout, 3. Exact move map (symbol → destination), 4. Test coupling — preserve or repoint (the real risk), 5. Watch-items (gotchas that will bite), 6. Phased execution with verification gates, 7. Explicitly out of scope (+13 more)

### Community 19 - "Grader Workflow UI"
Cohesion: 0.15
Nodes (10): Manual Classroom Posting (API limitation), GraderQueue(), GraderTopbar(), GraderWrap(), postingClipboardText(), scoreOf(), scoreOf, studentLabel (+2 more)

### Community 20 - "Grading Test Doubles"
Cohesion: 0.24
Nodes (15): infer_job_criteria(), _is_substantial_description(), Infer the rubric for an `infer`-mode job once, before drafting. Description, _CapturingEngine, _infer_provider(), _seed_infer_job(), test_grade_loop_no_longer_swaps_criteria(), test_infer_caps_sample_at_configured_size() (+7 more)

### Community 21 - "OAuth Token Management"
Cohesion: 0.26
Nodes (12): datetime, AccountProfile, _cache_hit(), get_google_provider(), Legacy single-user helper. Use make_google_provider() for multi-user flows., _ttl(), _TtlCacheEntry, log_cache_hit() (+4 more)

### Community 22 - "Frontend App State"
Cohesion: 0.16
Nodes (14): Active Job localStorage persistence, Draft Queue Seeding (stable alphabetical order), SSE Streaming for Grading Progress, App (React root), App grading state management, ConnectView, DoneView, DryRunDrawer (+6 more)

### Community 23 - "Content Extraction & Scrub"
Cohesion: 0.18
Nodes (8): extract_submission_content(), scrub_submission_cached(), run_grading_privacy_audit() endpoint, privacy_audit_snapshot(), run_privacy_audit(), pseudonym_for_submission(), ScrubbedSubmission, scrub_submission()

### Community 24 - "DeepSeek Model Config"
Cohesion: 0.18
Nodes (10): display_name, enabled, notes, rpm_limit, tpm_limit, use_cases, default_model, models (+2 more)

### Community 25 - "Draft Job Pipeline"
Cohesion: 0.25
Nodes (7): draft_grading_job(), _group_files(), _submission_for_file(), draft_job() endpoint, ensure_privacy_audit_allows_draft(), resolve_grading_engine(), stream_draft_job() endpoint

### Community 26 - "Resume & SSE Tests"
Cohesion: 0.33
Nodes (7): _sse_payloads helper, _create_job(), Coverage for the resume/preview additions: the global grading-jobs list and the, test_jobs_list_collapses_to_newest_per_activity(), test_jobs_list_surfaces_created_job(), test_submission_preview_forces_download_for_unsafe_type(), test_submission_preview_streams_image_inline()

### Community 27 - "Gemini 2.5 Config"
Cohesion: 0.29
Nodes (7): display_name, enabled, notes, rpm_limit, tpm_limit, use_cases, gemini/gemini-2.5-flash

### Community 28 - "Gemini Flash Lite Config"
Cohesion: 0.29
Nodes (7): display_name, enabled, notes, rpm_limit, tpm_limit, use_cases, gemini/gemini-3.1-flash-lite

### Community 29 - "OpenAI GPT-5 Config"
Cohesion: 0.29
Nodes (7): openai/gpt-5, display_name, enabled, notes, rpm_limit, tpm_limit, use_cases

### Community 30 - "xAI Grok Config"
Cohesion: 0.29
Nodes (7): xai/grok-4-1-fast-non-reasoning, display_name, enabled, notes, rpm_limit, tpm_limit, use_cases

### Community 31 - "Grading Stream Tests"
Cohesion: 0.29
Nodes (7): _sse_payloads(), test_criteria_stream_infers_before_audit(), test_draft_stream_emits_incremental_submissions_without_criteria_phase(), test_draft_stream_emits_per_submission_progress(), test_draft_stream_seeds_full_queue_in_stable_order(), test_privacy_audit_stream_emits_progress_and_terminal_event(), test_update_criteria_replaces_and_survives_reinference()

### Community 32 - "Test Cleanup & Token Store"
Cohesion: 0.21
Nodes (8): build_oauth_authorization_url(), clear_google_provider_caches(), byte_preview(), log_event(), log_warning(), auth_start(), Shared pytest configuration for the API test suite.  Two isolation concerns ar, _reset_global_state()

### Community 33 - "Submission Caching"
Cohesion: 0.33
Nodes (3): _attempt_metadata(), cache_submission_file(), _draft_submission()

### Community 34 - "Engine Readiness Probe"
Cohesion: 0.40
Nodes (5): get_grading_engine(), inspect_grading_readiness(), _missing_provider_keys(), load_llm_catalog(), _merge_models()

### Community 35 - "Provider Key Health Tests"
Cohesion: 0.33
Nodes (6): _enable_litellm_engine(), Point settings at a local single-model catalog with litellm selected.     conft, test_draft_returns_503_when_provider_key_missing(), test_grading_health_ready_when_provider_key_present(), test_grading_health_reports_missing_provider_key(), test_grading_health_reports_model_not_enabled()

### Community 36 - "App Initialization"
Cohesion: 0.40
Nodes (3): ensure_sqlite_dev_migrations(), init_db(), FastAPI app instance

### Community 37 - "Google Cache Management"
Cohesion: 0.40
Nodes (5): clear_google_provider_caches(), google_auth_http_exception(), list_courses() endpoint, purge_cached_classroom_state(), _reset_global_state() fixture

### Community 38 - "Drive Grouping Tests"
Cohesion: 0.53
Nodes (6): _is_fresh(), GoogleProvider, Session, UserSession, list_activities(), list_courses()

### Community 39 - "Browser File System Types"
Cohesion: 0.40
Nodes (4): FileSystemDirectoryHandle, FileSystemFileHandle, FileSystemWritableFileStream, Window

### Community 40 - "OAuth Auth URL"
Cohesion: 0.07
Nodes (78): _as_utc(), _cache_headers(), _conditional_response(), _etag(), _if_none_match(), _is_future(), SSE + generic HTTP-cache primitives.  No domain dependencies., _sse_event() (+70 more)

### Community 41 - "Claude Code Settings"
Cohesion: 0.41
Nodes (15): Path, Settings, load_llm_catalog(), MonkeyPatch, _catalog_settings(), _make_stale(), test_catalog_merges_upstream_cache_and_overlay(), test_estimate_cost_cents_uses_catalog_token_prices() (+7 more)

### Community 42 - "File Preview Tests"
Cohesion: 0.67
Nodes (3): _seed_preview_cache(), test_preview_binary_still_attachment(), test_preview_code_file_served_inline_as_text_plain()

### Community 53 - "Local Settings File"
Cohesion: 0.12
Nodes (21): GradingEngineRequest, LlmModelEntry, _build_rubric_messages(), LiteLlmGradingEngine, parse_litellm_result(), parse_litellm_result(), LLM Model Catalog (local/remote/cached modes), Rubric Inference (description-first vs sample-based) (+13 more)

### Community 60 - "Community 60"
Cohesion: 0.19
Nodes (9): GradingReadiness, inspect_grading_readiness(), _missing_provider_keys(), MockGradingEngine, _probe_valid_key(), Offline check via litellm.validate_environment: which provider env vars     the, Live check via litellm.check_valid_key. Returns (ok, detail); ok is None     wh, Non-raising readiness report for the configured grading engine. Used by     the (+1 more)

### Community 62 - "Community 62"
Cohesion: 0.33
Nodes (5): Backend Settings, Classroom Downloader, Development, Docker / Coolify deployment, Stack

## Knowledge Gaps
- **170 isolated node(s):** `schema_version`, `default_model`, `enabled`, `display_name`, `use_cases` (+165 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Teacher-Loop Modes (off/approve/auto/cowrite)` connect `Grader Review Panel` to `Test Fixtures & Settings`, `UI Component Library`?**
  _High betweenness centrality (0.159) - this node is a cross-community bridge._
- **Why does `Student Pseudonymization before AI` connect `Privacy & PII Protection` to `Grader Review Panel`, `Logging & Observability`, `Local Settings File`, `Test Fixtures & Settings`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Test Fixtures & Settings` to `Core Grading Pipeline`, `API Routes & Job Management`, `LLM Grading Engine`, `Privacy Audit System`, `Test Cleanup & Token Store`, `Provider Key Health Tests`, `LLM Model Catalog`, `OAuth Auth URL`, `Claude Code Settings`, `Database & Migrations`, `Logging & Observability`, `Grading Test Doubles`, `OAuth Token Management`, `Community 60`, `Grading Stream Tests`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Are the 60 inferred relationships involving `GradingStatus` (e.g. with `Activity` and `datetime`) actually correct?**
  _`GradingStatus` has 60 INFERRED edges - model-reasoned connections that need verification._
- **Are the 44 inferred relationships involving `GoogleProvider` (e.g. with `Activity` and `datetime`) actually correct?**
  _`GoogleProvider` has 44 INFERRED edges - model-reasoned connections that need verification._
- **Are the 54 inferred relationships involving `GradingJob` (e.g. with `Activity` and `datetime`) actually correct?**
  _`GradingJob` has 54 INFERRED edges - model-reasoned connections that need verification._
- **What connects `schema_version`, `default_model`, `enabled` to the rest of the system?**
  _208 weakly-connected nodes found - possible documentation gaps or missing edges._