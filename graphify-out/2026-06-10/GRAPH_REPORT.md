# Graph Report - .  (2026-06-09)

## Corpus Check
- Corpus is ~47,591 words - fits in a single context window. You may not need a graph.

## Summary
- 942 nodes · 3133 edges · 32 communities (31 shown, 1 thin omitted)
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 642 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

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

## God Nodes (most connected - your core abstractions)
1. `log_event()` - 93 edges
2. `get_settings()` - 87 edges
3. `GradingStatus` - 46 edges
4. `GoogleProvider` - 44 edges
5. `Session` - 42 edges
6. `GradingJob` - 41 edges
7. `GradingSubmission` - 41 edges
8. `GradingJob` - 37 edges
9. `SubmissionFile` - 36 edges
10. `GradingSubmission` - 33 edges

## Surprising Connections (you probably didn't know these)
- `UserSession` --uses--> `AuthFailure`  [INFERRED]
  apps/api/src/classroom_downloader/api/session_cleanup.py → apps/api/src/classroom_downloader/api/auth_errors.py
- `AuthFailure` --uses--> `AuthFailure`  [INFERRED]
  apps/api/src/classroom_downloader/api/session_cleanup.py → apps/api/src/classroom_downloader/api/auth_errors.py
- `Path` --uses--> `ClassroomCourse`  [INFERRED]
  apps/api/tests/test_grading.py → apps/api/src/classroom_downloader/google_provider.py
- `ClassroomCourse` --uses--> `UserSession`  [INFERRED]
  apps/api/src/classroom_downloader/google_provider.py → apps/api/src/classroom_downloader/models.py
- `_CapturingEngine` --uses--> `ClassroomCourse`  [INFERRED]
  apps/api/tests/test_grading.py → apps/api/src/classroom_downloader/google_provider.py

## Import Cycles
- 1-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/main.py`
- 1-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/api/deps.py`
- 1-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/api/common.py`
- 1-file cycle: `apps/api/src/classroom_downloader/google_provider.py -> apps/api/src/classroom_downloader/google_provider.py`
- 1-file cycle: `apps/api/src/classroom_downloader/grading.py -> apps/api/src/classroom_downloader/grading.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/deps.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/health.py -> apps/api/src/classroom_downloader/main.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/api/deps.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/api/deps.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/api/deps.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/api/deps.py`

## Hyperedges (group relationships)
- **api/ Support Layer (common, auth_errors, session_cleanup, deps)** — plan_api_common, plan_api_auth_errors, plan_api_session_cleanup, plan_api_deps [EXTRACTED 0.90]
- **Domain Routers by Bounded Context** — plan_routers_health, plan_routers_auth, plan_routers_courses, plan_routers_exports, plan_routers_grading [EXTRACTED 0.90]
- **One-Way Import Chain (main to routers to deps to api-support to services)** — plan_compat_reexports, plan_routers_grading, plan_api_deps, plan_api_session_cleanup, plan_api_auth_errors [EXTRACTED 0.85]

## Communities (32 total, 1 thin omitted)

### Community 0 - "Grading Domain & DB Models"
Cohesion: 0.12
Nodes (100): GradingFileCache, datetime, ExtractedSubmissionContent, GoogleProvider, GradingEngine, GradingFileCache, GradingJob, GradingJobRead (+92 more)

### Community 1 - "Persistence & API Dependencies"
Cohesion: 0.06
Nodes (63): AuthFailure, _contains_invalid_grant(), google_auth_http_exception(), _http_403_is_hard_auth_failure(), _http_error_content(), Google auth-error → HTTP translation.  Pure, no side effects., _as_utc(), get_current_session() (+55 more)

### Community 2 - "Grading Tests & Settings"
Cohesion: 0.06
Nodes (64): infer_job_criteria(), _is_substantial_description(), Infer the rubric for an `infer`-mode job once, before drafting. Description, get_settings(), _CapturingEngine, _enable_litellm_engine(), _infer_provider(), Point settings at a local single-model catalog with litellm selected.     conft (+56 more)

### Community 3 - "Grading Router & Job Snapshots"
Cohesion: 0.08
Nodes (63): _as_utc(), _cache_headers(), _conditional_response(), _etag(), _if_none_match(), _is_fresh(), _is_future(), SSE + generic HTTP-cache primitives.  No domain dependencies. (+55 more)

### Community 4 - "LiteLLM Grading Engine"
Cohesion: 0.08
Nodes (48): Any, GradingEngineRequest, LlmModelEntry, GradingEngineRequest, LlmModelEntry, get_grading_engine(), GradingEngineResult, GradingReadiness (+40 more)

### Community 5 - "LLM Catalog & Settings"
Cohesion: 0.13
Nodes (35): Any, Path, Settings, Path, Settings, BaseSettings, _bool_or_none(), _cache_is_stale() (+27 more)

### Community 6 - "Google Classroom Provider"
Cohesion: 0.11
Nodes (16): ClassroomActivity, ClassroomCourse, _due_label(), GoogleApiProvider, FakeClassroomService, FakeCourses, FakeCourseWork, FakeDriveFiles (+8 more)

### Community 7 - "LLM Model Overrides Config"
Cohesion: 0.05
Nodes (38): display_name, enabled, notes, rpm_limit, tpm_limit, use_cases, default_model, display_name (+30 more)

### Community 8 - "Schemas & Privacy Audit"
Cohesion: 0.20
Nodes (34): GoogleProvider, GradingJob, GradingSubmission, PrivacyAuditRead, Session, SubmissionFile, BaseModel, ExportStatus (+26 more)

### Community 9 - "Auth Flow & Token Store"
Cohesion: 0.11
Nodes (24): Request, Response, Session, AuthStart, AuthState, build_oauth_authorization_url(), clear_google_provider_caches(), DbTokenStore (+16 more)

### Community 10 - "Workspace Views (UI)"
Cohesion: 0.11
Nodes (19): HistoryView(), AppIcon(), IconName, icons, EmptyState(), SearchBox(), SkeletonRows(), ReferenceQueueCard() (+11 more)

### Community 11 - "App Shell & Flow Views (UI)"
Cohesion: 0.09
Nodes (15): ConnectView(), InlineError(), DoneView(), ProgressLogItem, ProgressView(), isFolderExportSupported(), useLocalExportHistory(), buildPreviewTree() (+7 more)

### Community 12 - "Frontend API Client & Export"
Cohesion: 0.09
Nodes (26): DryRunDrawer(), api, CacheEntry, cacheKey(), CacheOptions, fetchJson(), inFlight, request() (+18 more)

### Community 13 - "Grader Review UI"
Cohesion: 0.10
Nodes (23): BlockedEvidence(), extensionOf(), GraderReview(), hasDefaultCriteria(), initials(), INLINE_IMAGE_MIME, INLINE_TEXT_EXTENSIONS, INLINE_TEXT_MIME (+15 more)

### Community 14 - "Router Split Design (Docs)"
Cohesion: 0.10
Nodes (28): Graphify Codebase-Query Workflow, Project Knowledge Graph (graphify-out), api/auth_errors.py (auth-error to HTTP translation), api/common.py (SSE + HTTP-cache primitives), api/deps.py (FastAPI dependencies), api/session_cleanup.py (session + cache purge), App-Owned Aggregate Tier (GradingJob + children), Bounded Contexts (auth, classroom-read, exports, grading) (+20 more)

### Community 15 - "UI Primitives & Grader Setup"
Cohesion: 0.16
Nodes (16): Card(), CardContent(), CardDescription(), CardFooter(), CardHeader(), CardTitle(), cn(), RadioGroup() (+8 more)

### Community 16 - "Submission & Drive Hydration"
Cohesion: 0.16
Nodes (9): drive_files_from_submission(), _looks_like_user_id(), MockGoogleProvider, A bare numeric Google account id leaking in as a display name (e.g. when a, submission_links_from_submission(), SubmissionLink, safe_fields(), test_drive_files_carry_classroom_submission_id_for_grouping() (+1 more)

### Community 17 - "Web Package Dependencies"
Cohesion: 0.10
Nodes (19): dependencies, lucide-react, react, react-dom, vite, @vitejs/plugin-react, devDependencies, @types/react (+11 more)

### Community 18 - "Exports Router & File Naming"
Cohesion: 0.19
Nodes (17): GoogleProvider, Request, Response, Session, build_output_path(), sanitize_segment(), ExportCreate, ExportFile (+9 more)

### Community 19 - "TypeScript Config"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+10 more)

### Community 20 - "Privacy Redaction (PII)"
Cohesion: 0.18
Nodes (17): is_valid_cpf(), Validate a Brazilian CPF by its two mod-11 check digits., Unit tests for the pt-BR privacy scrubber (`classroom_downloader.privacy`).  The, _scrub(), test_clean_text_has_no_counts(), test_combined_redactions_report_all_categories(), test_email_redacted(), test_full_name_redacted_lone_first_name_preserved() (+9 more)

### Community 21 - "Provider Sessions & Cache Logging"
Cohesion: 0.29
Nodes (11): datetime, AccountProfile, _cache_hit(), _ttl(), _TtlCacheEntry, UserSession, log_cache_hit(), log_cache_miss() (+3 more)

### Community 22 - "Observability & Logging"
Cohesion: 0.23
Nodes (12): Any, _bounded_repr(), _bounded_text(), _format_event(), _format_value(), JsonEventFormatter, log_debug(), _safe_value() (+4 more)

### Community 23 - "Grader Shell (UI)"
Cohesion: 0.21
Nodes (6): GraderQueue(), GraderTopbar(), GraderWrap(), postingClipboardText(), scoreOf(), GradingJob

### Community 24 - "Navigation Rail & Theme"
Cohesion: 0.31
Nodes (6): getInitials(), Rail(), ThemeToggle(), AppView, AuthState, ThemeMode

### Community 25 - "Grading Resume Tests"
Cohesion: 0.39
Nodes (6): _create_job(), Coverage for the resume/preview additions: the global grading-jobs list and the, test_jobs_list_collapses_to_newest_per_activity(), test_jobs_list_surfaces_created_job(), test_submission_preview_forces_download_for_unsafe_type(), test_submission_preview_streams_image_inline()

### Community 26 - "Courses Router"
Cohesion: 0.38
Nodes (7): Activity, GoogleProvider, Session, UserSession, Course, list_activities(), list_courses()

### Community 27 - "Filesystem API Types"
Cohesion: 0.40
Nodes (4): FileSystemDirectoryHandle, FileSystemFileHandle, FileSystemWritableFileStream, Window

## Knowledge Gaps
- **116 isolated node(s):** `schema_version`, `default_model`, `enabled`, `display_name`, `use_cases` (+111 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `log_event()` connect `Auth Flow & Token Store` to `Grading Domain & DB Models`, `Persistence & API Dependencies`, `Grading Tests & Settings`, `Grading Router & Job Snapshots`, `LiteLLM Grading Engine`, `LLM Catalog & Settings`, `Google Classroom Provider`, `Schemas & Privacy Audit`, `Submission & Drive Hydration`, `Exports Router & File Naming`, `Provider Sessions & Cache Logging`, `Observability & Logging`, `Courses Router`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Grading Tests & Settings` to `Grading Domain & DB Models`, `Persistence & API Dependencies`, `Grading Router & Job Snapshots`, `LiteLLM Grading Engine`, `LLM Catalog & Settings`, `Auth Flow & Token Store`, `Provider Sessions & Cache Logging`, `Observability & Logging`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Why does `GoogleProvider` connect `Grading Domain & DB Models` to `Persistence & API Dependencies`, `Grading Router & Job Snapshots`, `Google Classroom Provider`, `Schemas & Privacy Audit`, `Auth Flow & Token Store`, `Submission & Drive Hydration`, `Provider Sessions & Cache Logging`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 41 inferred relationships involving `GradingStatus` (e.g. with `datetime` and `ExtractedSubmissionContent`) actually correct?**
  _`GradingStatus` has 41 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `GoogleProvider` (e.g. with `datetime` and `ExtractedSubmissionContent`) actually correct?**
  _`GoogleProvider` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `Session` (e.g. with `ExtractedSubmissionContent` and `GoogleProvider`) actually correct?**
  _`Session` has 22 INFERRED edges - model-reasoned connections that need verification._
- **What connects `schema_version`, `default_model`, `enabled` to the rest of the system?**
  _156 weakly-connected nodes found - possible documentation gaps or missing edges._