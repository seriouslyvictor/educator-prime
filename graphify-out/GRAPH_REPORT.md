# Graph Report - Classroom Downloader  (2026-06-11)

## Corpus Check
- 101 files · ~60,136 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1174 nodes · 3577 edges · 46 communities (42 shown, 4 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 497 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b3a2c626`
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
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 58|Community 58]]

## God Nodes (most connected - your core abstractions)
1. `log_event()` - 105 edges
2. `get_settings()` - 97 edges
3. `TestClient` - 90 edges
4. `GradingJob` - 37 edges
5. `GradingSubmission` - 37 edges
6. `GradingStatus` - 35 edges
7. `GoogleProvider` - 32 edges
8. `scrub_submission_cached()` - 32 edges
9. `safe_fields()` - 30 edges
10. `_CapturingEngine` - 29 edges

## Surprising Connections (you probably didn't know these)
- `test_build_sample_xml_wraps_and_escapes_samples()` --calls--> `build_sample_xml()`  [INFERRED]
  apps/api/tests/test_grading.py → apps/api/src/classroom_downloader/litellm_engine.py
- `GradingFileCache` --uses--> `GradingFileCache`  [INFERRED]
  apps/api/tests/test_zip_extraction.py → apps/api/src/classroom_downloader/models.py
- `test_courses_exclude_archived()` --calls--> `TestClient`  [INFERRED]
  apps/api/tests/test_api.py → apps/api/tests/test_queue_management_api.py
- `test_course_cache_logs_standard_hit_miss_pair()` --calls--> `TestClient`  [INFERRED]
  apps/api/tests/test_api.py → apps/api/tests/test_queue_management_api.py
- `test_export_creates_email_first_manifest_paths()` --calls--> `TestClient`  [INFERRED]
  apps/api/tests/test_api.py → apps/api/tests/test_queue_management_api.py

## Import Cycles
- 1-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/main.py`
- 1-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/api/deps.py`
- 1-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/api/common.py`
- 1-file cycle: `apps/api/src/classroom_downloader/google_provider.py -> apps/api/src/classroom_downloader/google_provider.py`
- 1-file cycle: `apps/api/src/classroom_downloader/grading/_common.py -> apps/api/src/classroom_downloader/grading/_common.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/deps.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/health.py -> apps/api/src/classroom_downloader/main.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/api/deps.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/api/auth_errors.py`

## Hyperedges (group relationships)
- **api/ Support Layer (common, auth_errors, session_cleanup, deps)** — plan_api_common, plan_api_auth_errors, plan_api_session_cleanup, plan_api_deps [EXTRACTED 0.90]
- **Domain Routers by Bounded Context** — plan_routers_health, plan_routers_auth, plan_routers_courses, plan_routers_exports, plan_routers_grading [EXTRACTED 0.90]
- **One-Way Import Chain (main to routers to deps to api-support to services)** — plan_compat_reexports, plan_routers_grading, plan_api_deps, plan_api_session_cleanup, plan_api_auth_errors [EXTRACTED 0.85]

## Communities (46 total, 4 thin omitted)

### Community 0 - "Grading Domain & DB Models"
Cohesion: 0.05
Nodes (99): GradingFileCache, Path, GradingAiAttempt, GradingEngine, GradingJob, GradingSubmission, Session, ExtractedSubmissionContent (+91 more)

### Community 1 - "Persistence & API Dependencies"
Cohesion: 0.07
Nodes (29): 0. Goal & context, 10. Watch-items (gotchas that will bite), 1. Files touched (overview), 2.1 `queue_state` column, 2.2 Dev migration, 2. Data model + migration (backend), 3.1 Enumerate the cascade (do not miss a table), 3.2 `delete_job(session, job) -> None` (+21 more)

### Community 2 - "Grading Tests & Settings"
Cohesion: 0.10
Nodes (54): get_settings(), TestClient, _sse_payloads(), test_brief_mode_sends_rubric_text_and_keeps_default_criteria(), test_build_sample_xml_wraps_and_escapes_samples(), test_classroom_links_endpoint_backfills_links_and_posted_state(), test_create_job_exposes_visual_submission_consent(), test_create_job_persists_teacher_criteria() (+46 more)

### Community 3 - "Grading Router & Job Snapshots"
Cohesion: 0.06
Nodes (79): _as_utc(), _cache_headers(), _conditional_response(), _etag(), _if_none_match(), _is_fresh(), _is_future(), SSE + generic HTTP-cache primitives.  No domain dependencies. (+71 more)

### Community 4 - "LiteLLM Grading Engine"
Cohesion: 0.06
Nodes (78): Path, Any, GradingEngineRequest, LlmModelEntry, VisionExtractionResult, Path, GradingEngineRequest, LlmModelEntry (+70 more)

### Community 5 - "LLM Catalog & Settings"
Cohesion: 0.14
Nodes (34): Any, Path, Settings, Path, Settings, BaseSettings, _bool_or_none(), _cache_is_stale() (+26 more)

### Community 6 - "Google Classroom Provider"
Cohesion: 0.17
Nodes (12): ClassroomActivity, ClassroomCourse, FakeClassroomService, FakeCourses, FakeCourseWork, FakeDriveFiles, FakeDriveService, FakeExecute (+4 more)

### Community 7 - "LLM Model Overrides Config"
Cohesion: 0.05
Nodes (38): display_name, enabled, notes, rpm_limit, tpm_limit, use_cases, default_model, display_name (+30 more)

### Community 8 - "Schemas & Privacy Audit"
Cohesion: 0.06
Nodes (112): AuthFailure, _contains_invalid_grant(), google_auth_http_exception(), _http_403_is_hard_auth_failure(), _http_error_content(), Google auth-error → HTTP translation.  Pure, no side effects., _as_utc(), get_current_session() (+104 more)

### Community 9 - "Auth Flow & Token Store"
Cohesion: 0.15
Nodes (34): Path, GradingFileCache, Path, _decode_entry(), _display_name(), extract_zip_submission(), _is_noise(), _is_safe_entry_name() (+26 more)

### Community 10 - "Workspace Views (UI)"
Cohesion: 0.09
Nodes (21): HistoryView(), EmptyState(), SearchBox(), SkeletonRows(), actionsForItem(), bulkActions, CardMenu(), QueueActionConfig (+13 more)

### Community 11 - "App Shell & Flow Views (UI)"
Cohesion: 0.09
Nodes (20): DryRunDrawer(), api, ensureDirectory(), exportJobToFolder(), isFolderExportSupported(), pickExportFolder(), writeExportFile(), useLocalExportHistory() (+12 more)

### Community 12 - "Frontend API Client & Export"
Cohesion: 0.11
Nodes (23): getInitials(), Rail(), ThemeToggle(), CacheEntry, cacheKey(), CacheOptions, fetchJson(), inFlight (+15 more)

### Community 13 - "Grader Review UI"
Cohesion: 0.10
Nodes (25): BlockedEvidence(), extensionOf(), GraderReview(), hasDefaultCriteria(), initials(), INLINE_IMAGE_MIME, INLINE_TEXT_EXTENSIONS, INLINE_TEXT_MIME (+17 more)

### Community 14 - "Router Split Design (Docs)"
Cohesion: 0.10
Nodes (28): Graphify Codebase-Query Workflow, Project Knowledge Graph (graphify-out), api/auth_errors.py (auth-error to HTTP translation), api/common.py (SSE + HTTP-cache primitives), api/deps.py (FastAPI dependencies), api/session_cleanup.py (session + cache purge), App-Owned Aggregate Tier (GradingJob + children), Bounded Contexts (auth, classroom-read, exports, grading) (+20 more)

### Community 15 - "UI Primitives & Grader Setup"
Cohesion: 0.16
Nodes (16): Card(), CardContent(), CardDescription(), CardFooter(), CardHeader(), CardTitle(), cn(), RadioGroup() (+8 more)

### Community 16 - "Submission & Drive Hydration"
Cohesion: 0.22
Nodes (6): _due_label(), GoogleApiProvider, MockGoogleProvider, byte_preview(), log_event(), safe_fields()

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
Cohesion: 0.22
Nodes (11): datetime, AccountProfile, drive_files_from_submission(), _looks_like_user_id(), A bare numeric Google account id leaking in as a display name (e.g. when a, submission_links_from_submission(), SubmissionLink, UserSession (+3 more)

### Community 22 - "Observability & Logging"
Cohesion: 0.29
Nodes (15): Any, _cache_hit(), _ttl(), _TtlCacheEntry, _bounded_repr(), _bounded_text(), _format_event(), _format_value() (+7 more)

### Community 23 - "Grader Shell (UI)"
Cohesion: 0.21
Nodes (6): GraderQueue(), GraderTopbar(), GraderWrap(), postingClipboardText(), scoreOf(), GradingJob

### Community 24 - "Navigation Rail & Theme"
Cohesion: 0.16
Nodes (21): GoogleProvider, GradingCriterion, GradingEngine, GradingJob, Session, _collect_inference_samples(), infer_job_criteria(), Reuse the audit's cached + scrubbed content to build a privacy-safe sample. (+13 more)

### Community 25 - "Grading Resume Tests"
Cohesion: 0.39
Nodes (7): _create_job(), Coverage for the resume/preview additions: the global grading-jobs list and the, test_jobs_list_collapses_to_newest_per_activity(), test_jobs_list_surfaces_created_job(), test_submission_preview_forces_download_for_unsafe_type(), test_submission_preview_streams_image_inline(), test_submission_preview_unknown_job_is_404()

### Community 26 - "Courses Router"
Cohesion: 0.38
Nodes (7): Activity, GoogleProvider, Session, UserSession, Course, list_activities(), list_courses()

### Community 27 - "Filesystem API Types"
Cohesion: 0.40
Nodes (4): FileSystemDirectoryHandle, FileSystemFileHandle, FileSystemWritableFileStream, Window

### Community 32 - "Community 32"
Cohesion: 0.16
Nodes (17): Request, Response, Session, AuthStart, AuthState, build_oauth_authorization_url(), DbTokenStore, make_google_provider() (+9 more)

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (8): ConnectView(), InlineError(), DoneView(), AppIcon(), IconName, icons, ProgressLogItem, ProgressView()

### Community 34 - "Community 34"
Cohesion: 0.42
Nodes (12): _ensure_activity_columns(), _ensure_cache_columns(), _ensure_columns(), _ensure_grading_ai_attempt_columns(), _ensure_grading_criterion_columns(), _ensure_grading_job_columns(), _ensure_grading_submission_columns(), _ensure_privacy_columns() (+4 more)

### Community 35 - "Community 35"
Cohesion: 0.16
Nodes (13): init_db(), test_auth_me_profile_failure_keeps_loadable_google_token_signed_in(), test_course_cache_logs_standard_hit_miss_pair(), test_courses_exclude_archived(), test_courses_reports_expired_google_session_as_unauthorized(), test_export_creates_email_first_manifest_paths(), test_file_content_stream_uses_private_etag_cache(), test_file_content_streams() (+5 more)

### Community 36 - "Community 36"
Cohesion: 0.19
Nodes (6): clear_google_provider_caches(), get_google_provider(), Legacy single-user helper. Use make_google_provider() for multi-user flows., TokenStore, Shared pytest configuration for the API test suite.  Two isolation concerns ar, _reset_global_state()

### Community 37 - "Community 37"
Cohesion: 0.19
Nodes (9): _enable_litellm_engine(), Point settings at a local single-model catalog with litellm selected.     conft, _seed_preview_cache(), test_draft_returns_503_when_provider_key_missing(), test_grading_health_ready_when_provider_key_present(), test_grading_health_reports_missing_provider_key(), test_grading_health_reports_model_not_enabled(), test_preview_binary_still_attachment() (+1 more)

### Community 38 - "Community 38"
Cohesion: 0.29
Nodes (5): JsonEventFormatter, LogRecord, test_json_event_formatter_serializes_event_and_fields(), test_log_event_redacts_sensitive_field_names(), test_safe_fields_redacts_student_identity_and_bounds_values()

### Community 39 - "Community 39"
Cohesion: 0.60
Nodes (5): _create_job(), _seed_job_children(), test_archive_hide_restore_and_state_filters(), test_delete_grading_job_removes_all_children_and_cache_dir(), test_queue_state_is_present_in_jobs_and_queue_payloads()

### Community 51 - "Community 51"
Cohesion: 0.33
Nodes (5): Backend Settings, Classroom Downloader, Development, Docker / Coolify deployment, Stack

### Community 58 - "Community 58"
Cohesion: 0.08
Nodes (24): 0. Goal & context, 10. Watch-items (gotchas that will bite), 1. Files touched (overview), 2. Sentry (backend), 3.1 Structured extras (no console change), 3.2 Request/user context (contextvars), 3.3 The DB sink, 3.4 Retention (+16 more)

## Knowledge Gaps
- **184 isolated node(s):** `schema_version`, `default_model`, `enabled`, `display_name`, `use_cases` (+179 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `log_event()` connect `Submission & Drive Hydration` to `Grading Domain & DB Models`, `Community 32`, `Grading Router & Job Snapshots`, `Community 36`, `LiteLLM Grading Engine`, `LLM Catalog & Settings`, `Community 38`, `Schemas & Privacy Audit`, `Auth Flow & Token Store`, `Exports Router & File Naming`, `Provider Sessions & Cache Logging`, `Observability & Logging`, `Navigation Rail & Theme`, `Courses Router`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Grading Tests & Settings` to `Community 32`, `Grading Domain & DB Models`, `Community 34`, `Grading Router & Job Snapshots`, `Community 36`, `LiteLLM Grading Engine`, `LLM Catalog & Settings`, `Community 37`, `Schemas & Privacy Audit`, `Community 38`, `Submission & Drive Hydration`, `Provider Sessions & Cache Logging`, `Observability & Logging`, `Navigation Rail & Theme`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `TestClient` connect `Grading Tests & Settings` to `Grading Domain & DB Models`, `Community 35`, `Community 37`, `Community 39`, `Schemas & Privacy Audit`, `Grading Resume Tests`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 85 inferred relationships involving `TestClient` (e.g. with `GradingAiAttempt` and `GradingCriterion`) actually correct?**
  _`TestClient` has 85 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `GradingJob` (e.g. with `GoogleProvider` and `GradingJob`) actually correct?**
  _`GradingJob` has 23 INFERRED edges - model-reasoned connections that need verification._
- **What connects `schema_version`, `default_model`, `enabled` to the rest of the system?**
  _225 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Grading Domain & DB Models` be split into smaller, more focused modules?**
  _Cohesion score 0.05399792315680166 - nodes in this community are weakly interconnected._