# Graph Report - Classroom Downloader  (2026-06-12)

## Corpus Check
- 137 files · ~71,563 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1839 nodes · 4693 edges · 101 communities (96 shown, 5 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 557 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8abc035f`
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
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 109|Community 109]]
- [[_COMMUNITY_Community 113|Community 113]]

## God Nodes (most connected - your core abstractions)
1. `get_settings()` - 110 edges
2. `log_event()` - 107 edges
3. `TestClient` - 99 edges
4. `GradingJob` - 41 edges
5. `GradingSubmission` - 41 edges
6. `GradingStatus` - 39 edges
7. `GoogleProvider` - 32 edges
8. `scrub_submission_cached()` - 32 edges
9. `log_warning()` - 32 edges
10. `ExportStatus` - 30 edges

## Surprising Connections (you probably didn't know these)
- `test_google_auth_failures_return_codes()` --calls--> `google_auth_http_exception()`  [INFERRED]
  apps/api/tests/test_error_contract.py → apps/api/src/classroom_downloader/api/auth_errors.py
- `test_api_error_uses_structured_detail()` --calls--> `api_error()`  [INFERRED]
  apps/api/tests/test_error_contract.py → apps/api/src/classroom_downloader/api/errors.py
- `test_google_api_classifier_maps_rate_limit_and_unavailable()` --calls--> `google_api_http_exception()`  [INFERRED]
  apps/api/tests/test_error_contract.py → apps/api/src/classroom_downloader/api/google_errors.py
- `GradingFileCache` --uses--> `GradingFileCache`  [INFERRED]
  apps/api/tests/test_zip_extraction.py → apps/api/src/classroom_downloader/models.py
- `test_courses_exclude_archived()` --calls--> `TestClient`  [INFERRED]
  apps/api/tests/test_api.py → apps/api/tests/test_queue_management_api.py

## Import Cycles
- 1-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/main.py`
- 1-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/api/deps.py`
- 1-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/api/common.py`
- 1-file cycle: `apps/api/src/classroom_downloader/google_provider.py -> apps/api/src/classroom_downloader/google_provider.py`
- 1-file cycle: `apps/api/src/classroom_downloader/routers/admin.py -> apps/api/src/classroom_downloader/routers/admin.py`
- 1-file cycle: `apps/api/src/classroom_downloader/grading/_common.py -> apps/api/src/classroom_downloader/grading/_common.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/health.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/admin.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/deps.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/api/errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/errors.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/main.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/admin.py -> apps/api/src/classroom_downloader/api/deps.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/api/common.py`

## Hyperedges (group relationships)
- **api/ Support Layer (common, auth_errors, session_cleanup, deps)** — plan_api_common, plan_api_auth_errors, plan_api_session_cleanup, plan_api_deps [EXTRACTED 0.90]
- **Domain Routers by Bounded Context** — plan_routers_health, plan_routers_auth, plan_routers_courses, plan_routers_exports, plan_routers_grading [EXTRACTED 0.90]
- **One-Way Import Chain (main to routers to deps to api-support to services)** — plan_compat_reexports, plan_routers_grading, plan_api_deps, plan_api_session_cleanup, plan_api_auth_errors [EXTRACTED 0.85]

## Communities (101 total, 5 thin omitted)

### Community 0 - "Grading Domain & DB Models"
Cohesion: 0.09
Nodes (16): AttemptFilters, AttemptSheet(), EventFilters, EventSheet(), formatCost(), formatDate(), prettyJson(), shortId() (+8 more)

### Community 1 - "Persistence & API Dependencies"
Cohesion: 0.19
Nodes (26): ExtractedSubmissionContent, GoogleProvider, GradingEngine, GradingFileCache, GradingJob, GradingSubmission, Session, SubmissionFile (+18 more)

### Community 2 - "Grading Tests & Settings"
Cohesion: 0.09
Nodes (59): get_settings(), TestClient, _enable_litellm_engine(), Point settings at a local single-model catalog with litellm selected.     conft, _sse_payloads(), test_brief_mode_sends_rubric_text_and_keeps_default_criteria(), test_classroom_links_endpoint_backfills_links_and_posted_state(), test_create_job_exposes_visual_submission_consent() (+51 more)

### Community 3 - "Grading Router & Job Snapshots"
Cohesion: 0.06
Nodes (77): _as_utc(), _cache_headers(), _conditional_response(), _etag(), _if_none_match(), _is_future(), SSE + generic HTTP-cache primitives.  No domain dependencies., _sse_event() (+69 more)

### Community 4 - "LiteLLM Grading Engine"
Cohesion: 0.06
Nodes (81): Path, Any, GradingEngineRequest, LlmModelEntry, VisionExtractionResult, Path, GradingEngineRequest, LlmModelEntry (+73 more)

### Community 5 - "LLM Catalog & Settings"
Cohesion: 0.14
Nodes (34): Any, Path, Settings, Path, Settings, BaseSettings, _bool_or_none(), _cache_is_stale() (+26 more)

### Community 6 - "Google Classroom Provider"
Cohesion: 0.13
Nodes (21): AuthFailure, purge_cached_classroom_state_for_user(), purge_google_session_if_needed(), Session + provider + filesystem cache purge (side-effectful)., Session, UserSession, Session, datetime (+13 more)

### Community 7 - "LLM Model Overrides Config"
Cohesion: 0.05
Nodes (38): display_name, enabled, notes, rpm_limit, tpm_limit, use_cases, default_model, display_name (+30 more)

### Community 8 - "Schemas & Privacy Audit"
Cohesion: 0.16
Nodes (10): drive_files_from_submission(), _due_label(), _looks_like_user_id(), MockGoogleProvider, A bare numeric Google account id leaking in as a display name (e.g. when a, byte_preview(), log_event(), safe_fields() (+2 more)

### Community 9 - "Auth Flow & Token Store"
Cohesion: 0.15
Nodes (34): Path, GradingFileCache, Path, _decode_entry(), _display_name(), extract_zip_submission(), _is_noise(), _is_safe_entry_name() (+26 more)

### Community 10 - "Workspace Views (UI)"
Cohesion: 0.08
Nodes (21): HistoryView(), EmptyState(), SearchBox(), SkeletonRows(), actionsForItem(), bulkActions, CardMenu(), GraderQueue() (+13 more)

### Community 11 - "App Shell & Flow Views (UI)"
Cohesion: 0.06
Nodes (34): AdminView(), ConnectView(), DoneView(), DryRunDrawer(), AppIcon(), IconName, icons, ProgressLogItem (+26 more)

### Community 12 - "Frontend API Client & Export"
Cohesion: 0.09
Nodes (29): CacheEntry, cacheKey(), CacheOptions, checkAppVersion(), connectivityListeners, fetchJson(), inFlight, markConnectivityFailure() (+21 more)

### Community 13 - "Grader Review UI"
Cohesion: 0.10
Nodes (24): BlockedEvidence(), extensionOf(), GraderReview(), hasDefaultCriteria(), initials(), INLINE_IMAGE_MIME, INLINE_TEXT_EXTENSIONS, INLINE_TEXT_MIME (+16 more)

### Community 14 - "Router Split Design (Docs)"
Cohesion: 0.10
Nodes (28): Graphify Codebase-Query Workflow, Project Knowledge Graph (graphify-out), api/auth_errors.py (auth-error to HTTP translation), api/common.py (SSE + HTTP-cache primitives), api/deps.py (FastAPI dependencies), api/session_cleanup.py (session + cache purge), App-Owned Aggregate Tier (GradingJob + children), Bounded Contexts (auth, classroom-read, exports, grading) (+20 more)

### Community 15 - "UI Primitives & Grader Setup"
Cohesion: 0.14
Nodes (19): Card(), CardContent(), CardDescription(), CardFooter(), CardHeader(), CardTitle(), cn(), RadioGroup() (+11 more)

### Community 16 - "Submission & Drive Hydration"
Cohesion: 0.11
Nodes (16): GraderTopbar(), GraderWrap(), postingClipboardText(), scoreOf(), Phase, PostingPiP(), PostingPiPCard(), PostingPiPProps (+8 more)

### Community 17 - "Web Package Dependencies"
Cohesion: 0.06
Nodes (31): dependencies, class-variance-authority, clsx, @fontsource-variable/merriweather, @fontsource-variable/montserrat, lucide-react, next-themes, radix-ui (+23 more)

### Community 18 - "Exports Router & File Naming"
Cohesion: 0.15
Nodes (14): ClassroomActivity, ClassroomCourse, GoogleApiProvider, FakeClassroomService, FakeCourses, FakeCourseWork, FakeDriveFiles, FakeDriveService (+6 more)

### Community 19 - "TypeScript Config"
Cohesion: 0.09
Nodes (21): compilerOptions, allowJs, allowSyntheticDefaultImports, baseUrl, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx (+13 more)

### Community 20 - "Privacy Redaction (PII)"
Cohesion: 0.07
Nodes (30): properties, required, title, type, format, title, type, title (+22 more)

### Community 21 - "Provider Sessions & Cache Logging"
Cohesion: 0.25
Nodes (19): Any, Session, UserSession, AppEvent, GradingAiAttemptPayload, _bounded_repr(), _bounded_text(), configure_logging() (+11 more)

### Community 22 - "Observability & Logging"
Cohesion: 0.13
Nodes (42): AdminStats, AiAttemptAdminRead, AiAttemptPayloadRead, GradingAiAttempt, GradingSubmission, GradingSubmissionFile, AppEvent, datetime (+34 more)

### Community 23 - "Grader Shell (UI)"
Cohesion: 0.17
Nodes (16): Exception, Request, Request, Response, Session, AuthState, _is_database_locked(), sqlalchemy_operational_error_handler() (+8 more)

### Community 24 - "Navigation Rail & Theme"
Cohesion: 0.20
Nodes (19): GoogleProvider, GradingCriterion, GradingEngine, GradingJob, Session, _collect_inference_samples(), infer_job_criteria(), Reuse the audit's cached + scrubbed content to build a privacy-safe sample. (+11 more)

### Community 25 - "Grading Resume Tests"
Cohesion: 0.39
Nodes (7): _create_job(), Coverage for the resume/preview additions: the global grading-jobs list and the, test_jobs_list_collapses_to_newest_per_activity(), test_jobs_list_surfaces_created_job(), test_submission_preview_forces_download_for_unsafe_type(), test_submission_preview_streams_image_inline(), test_submission_preview_unknown_job_is_404()

### Community 26 - "Courses Router"
Cohesion: 0.12
Nodes (17): title, type, properties, anyOf, title, anyOf, title, default (+9 more)

### Community 27 - "Filesystem API Types"
Cohesion: 0.40
Nodes (4): FileSystemDirectoryHandle, FileSystemFileHandle, FileSystemWritableFileStream, Window

### Community 32 - "Community 32"
Cohesion: 0.60
Nodes (5): _create_job(), _seed_job_children(), test_archive_hide_restore_and_state_filters(), test_delete_grading_job_removes_all_children_and_cache_dir(), test_queue_state_is_present_in_jobs_and_queue_payloads()

### Community 33 - "Community 33"
Cohesion: 0.09
Nodes (21): aliases, components, hooks, lib, ui, utils, iconLibrary, menuAccent (+13 more)

### Community 34 - "Community 34"
Cohesion: 0.30
Nodes (14): GoogleProvider, Request, Response, Session, ExportCreate, ExportFile, ExportJobRead, _build_export_read() (+6 more)

### Community 35 - "Community 35"
Cohesion: 0.15
Nodes (14): init_db(), test_auth_me_profile_failure_keeps_loadable_google_token_signed_in(), test_course_cache_logs_standard_hit_miss_pair(), test_courses_exclude_archived(), test_courses_reports_expired_google_session_as_unauthorized(), test_export_creates_email_first_manifest_paths(), test_file_content_stream_uses_private_etag_cache(), test_file_content_streams() (+6 more)

### Community 36 - "Community 36"
Cohesion: 0.19
Nodes (17): Path, GradingJob, Session, Activity, Course, ExportError, ExportFile, ExportJob (+9 more)

### Community 37 - "Community 37"
Cohesion: 0.40
Nodes (10): GradingFileCache, Path, _decode_text(), extract_submission_content(), _extract_zip_content(), _is_zip_submission(), _safe_source_label(), text_preview() (+2 more)

### Community 38 - "Community 38"
Cohesion: 0.35
Nodes (12): GradingCriterion, Session, GradingCriterion, GradingCriterionInput, _apply_criterion_notes(), _criteria_match_defaults(), ensure_default_criteria(), _is_substantial_description() (+4 more)

### Community 39 - "Community 39"
Cohesion: 0.36
Nodes (13): GradingAiAttempt, GradingJob, GradingSubmission, Session, Session, _record_attempt(), _clear_rows(), DummyEngine (+5 more)

### Community 40 - "Community 40"
Cohesion: 0.06
Nodes (36): title, type, title, type, anyOf, title, anyOf, title (+28 more)

### Community 41 - "Community 41"
Cohesion: 0.24
Nodes (18): GoogleProvider, GradingJob, GradingSubmission, PrivacyAuditRead, Session, SubmissionFile, GoogleProvider, SubmissionFile (+10 more)

### Community 42 - "Community 42"
Cohesion: 0.53
Nodes (4): build_output_path(), sanitize_segment(), test_build_output_path_deduplicates_without_overwrite(), test_sanitize_segment_removes_filesystem_hostile_characters()

### Community 43 - "Community 43"
Cohesion: 0.11
Nodes (19): type, properties, required, title, type, title, type, title (+11 more)

### Community 44 - "Community 44"
Cohesion: 0.50
Nodes (3): _scrub_sentry_event(), test_scrub_sentry_event_never_raises_on_weird_shapes(), test_scrub_sentry_event_redacts_sensitive_shapes()

### Community 45 - "Community 45"
Cohesion: 0.08
Nodes (23): required, title, type, components, schemas, required, title, type (+15 more)

### Community 46 - "Community 46"
Cohesion: 0.30
Nodes (4): _seed_preview_cache(), test_mock_infer_rubric_returns_weighted_criteria(), test_preview_binary_still_attachment(), test_preview_code_file_served_inline_as_text_plain()

### Community 47 - "Community 47"
Cohesion: 0.12
Nodes (17): properties, required, title, type, anyOf, title, due_label, state (+9 more)

### Community 48 - "Community 48"
Cohesion: 0.17
Nodes (11): cn(), InputGroup(), InputGroupAddon(), inputGroupAddonVariants, InputGroupButton(), inputGroupButtonVariants, InputGroupInput(), Input() (+3 more)

### Community 49 - "Community 49"
Cohesion: 0.09
Nodes (23): anyOf, title, properties, required, title, type, properties, required (+15 more)

### Community 50 - "Community 50"
Cohesion: 0.18
Nodes (17): is_valid_cpf(), Validate a Brazilian CPF by its two mod-11 check digits., Unit tests for the pt-BR privacy scrubber (`classroom_downloader.privacy`).  The, _scrub(), test_clean_text_has_no_counts(), test_combined_redactions_report_all_categories(), test_email_redacted(), test_full_name_redacted_lone_first_name_preserved() (+9 more)

### Community 51 - "Community 51"
Cohesion: 0.33
Nodes (5): Backend Settings, Classroom Downloader, Development, Docker / Coolify deployment, Stack

### Community 54 - "Community 54"
Cohesion: 0.14
Nodes (14): properties, required, title, type, anyOf, title, title, type (+6 more)

### Community 55 - "Community 55"
Cohesion: 0.10
Nodes (20): properties, required, title, type, title, type, title, type (+12 more)

### Community 58 - "Community 58"
Cohesion: 0.19
Nodes (24): GradingEngine, ExtractedSubmissionContent, GoogleProvider, GradingEngine, GradingJob, GradingSubmission, Session, SubmissionFile (+16 more)

### Community 59 - "Community 59"
Cohesion: 0.18
Nodes (11): anyOf, title, title, type, properties, required, title, type (+3 more)

### Community 60 - "Community 60"
Cohesion: 0.18
Nodes (11): title, type, properties, required, title, type, course_state, section (+3 more)

### Community 61 - "Community 61"
Cohesion: 0.08
Nodes (26): title, type, anyOf, title, anyOf, title, properties, required (+18 more)

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (26): title, type, title, type, anyOf, title, title, type (+18 more)

### Community 63 - "Community 63"
Cohesion: 0.22
Nodes (9): anyOf, title, type, properties, required, title, type, criteria (+1 more)

### Community 64 - "Community 64"
Cohesion: 0.12
Nodes (16): properties, anyOf, title, anyOf, title, anyOf, title, title (+8 more)

### Community 65 - "Community 65"
Cohesion: 0.30
Nodes (21): ExtractedSubmissionContent, GradingJob, GradingSubmission, Session, GradingJob, GradingSubmission, ExtractedSubmissionContent, GradingJob (+13 more)

### Community 66 - "Community 66"
Cohesion: 0.21
Nodes (21): AppEvent, _ensure_activity_columns(), _ensure_cache_columns(), _ensure_columns(), _ensure_grading_ai_attempt_columns(), _ensure_grading_criterion_columns(), _ensure_grading_job_columns(), _ensure_grading_submission_columns() (+13 more)

### Community 67 - "Community 67"
Cohesion: 0.20
Nodes (6): DbTokenStore, get_google_provider(), make_google_provider(), Legacy single-user helper. Use make_google_provider() for multi-user flows., Loads and refreshes Google credentials stored in the UserSession DB row., TokenStore

### Community 68 - "Community 68"
Cohesion: 0.15
Nodes (6): Field(), FieldGroup(), FieldLabel(), fieldVariants, Label(), Separator()

### Community 69 - "Community 69"
Cohesion: 0.50
Nodes (4): default, title, type, is_admin

### Community 70 - "Community 70"
Cohesion: 0.14
Nodes (14): properties, required, title, type, title, type, title, type (+6 more)

### Community 71 - "Community 71"
Cohesion: 0.16
Nodes (7): Button(), buttonVariants, Sheet(), SheetContent(), SheetDescription(), SheetHeader(), SheetTitle()

### Community 72 - "Community 72"
Cohesion: 0.29
Nodes (9): api, ensureDirectory(), errorReason(), ExportFolderSummary, exportJobToFolder(), isFatalExportError(), pickExportFolder(), writeExportFile() (+1 more)

### Community 73 - "Community 73"
Cohesion: 0.09
Nodes (22): anyOf, title, properties, required, title, type, type, default (+14 more)

### Community 74 - "Community 74"
Cohesion: 0.22
Nodes (7): test_api_error_uses_structured_detail(), test_google_api_classifier_maps_rate_limit_and_unavailable(), test_google_auth_failures_return_codes(), test_llm_budget_exhausted_is_non_retryable(), test_missing_session_returns_not_signed_in_code(), test_oauth_not_configured_returns_code(), test_responses_include_app_version_header()

### Community 75 - "Community 75"
Cohesion: 0.18
Nodes (6): Select(), SelectContent(), SelectGroup(), SelectItem(), SelectTrigger(), SelectValue()

### Community 76 - "Community 76"
Cohesion: 0.50
Nodes (4): provider, anyOf, title, type

### Community 77 - "Community 77"
Cohesion: 0.50
Nodes (4): retryable, default, title, type

### Community 78 - "Community 78"
Cohesion: 0.67
Nodes (3): anyOf, title, email

### Community 79 - "Community 79"
Cohesion: 0.36
Nodes (6): Card(), CardContent(), CardDescription(), CardFooter(), CardHeader(), CardTitle()

### Community 80 - "Community 80"
Cohesion: 0.67
Nodes (3): title, type, engine

### Community 81 - "Community 81"
Cohesion: 0.21
Nodes (17): GradingJob, GradingSubmission, GradingSubmissionFile, Session, SubmissionFile, GradingSubmissionFile, One attachment within a grouped submission. A student who submits multiple, grading_submission_snapshot() (+9 more)

### Community 83 - "Community 83"
Cohesion: 0.08
Nodes (26): title, type, title, type, items, default, items, title (+18 more)

### Community 84 - "Community 84"
Cohesion: 0.47
Nodes (8): _clear_rows(), _seed_admin_rows(), _session_for(), test_admin_routes_allow_admin_and_filter_results(), test_auth_me_reports_is_admin_from_allowlist(), test_mock_provider_is_allowed_for_admin_api(), test_non_admin_gets_403_on_admin_routes(), test_payload_returns_404_after_purge()

### Community 85 - "Community 85"
Cohesion: 0.19
Nodes (7): ErrorBoundary, Props, State, FullError(), Gate(), OfflinePill(), index.html (SPA shell)

### Community 86 - "Community 86"
Cohesion: 0.29
Nodes (6): Empty(), EmptyDescription(), EmptyHeader(), EmptyMedia(), emptyMediaVariants, EmptyTitle()

### Community 87 - "Community 87"
Cohesion: 0.19
Nodes (17): Activity, _is_fresh(), google_api_http_exception(), Exception, HTTPException, GoogleProvider, Session, UserSession (+9 more)

### Community 88 - "Community 88"
Cohesion: 0.40
Nodes (5): Tabs(), TabsContent(), TabsList(), tabsListVariants, TabsTrigger()

### Community 89 - "Community 89"
Cohesion: 0.50
Nodes (4): default, title, type, batch_mode

### Community 92 - "Community 92"
Cohesion: 0.50
Nodes (4): default, title, type, has_payload

### Community 94 - "Community 94"
Cohesion: 0.50
Nodes (4): retry_count, default, title, type

### Community 97 - "Community 97"
Cohesion: 0.67
Nodes (3): anyOf, title, cost_cents

### Community 98 - "Community 98"
Cohesion: 0.67
Nodes (3): safe_error, anyOf, title

### Community 99 - "Community 99"
Cohesion: 0.67
Nodes (3): stage, title, type

### Community 100 - "Community 100"
Cohesion: 0.67
Nodes (3): title, type, extraction_status

### Community 101 - "Community 101"
Cohesion: 0.67
Nodes (3): anyOf, title, latency_ms

### Community 102 - "Community 102"
Cohesion: 0.67
Nodes (3): title, type, privacy_status

### Community 103 - "Community 103"
Cohesion: 0.67
Nodes (3): anyOf, title, prompt_tokens

### Community 109 - "Community 109"
Cohesion: 0.07
Nodes (42): _contains_invalid_grant(), google_auth_http_exception(), _http_403_is_hard_auth_failure(), _http_error_content(), Google auth-error → HTTP translation.  Pure, no side effects., admin_email_set(), _as_utc(), get_current_session() (+34 more)

## Knowledge Gaps
- **463 isolated node(s):** `schema_version`, `default_model`, `enabled`, `display_name`, `use_cases` (+458 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `log_event()` connect `Schemas & Privacy Audit` to `Persistence & API Dependencies`, `Grading Router & Job Snapshots`, `LiteLLM Grading Engine`, `LLM Catalog & Settings`, `Google Classroom Provider`, `Auth Flow & Token Store`, `Exports Router & File Naming`, `Provider Sessions & Cache Logging`, `Grader Shell (UI)`, `Navigation Rail & Theme`, `Community 34`, `Community 37`, `Community 38`, `Community 39`, `Community 41`, `Community 58`, `Community 65`, `Community 66`, `Community 67`, `Community 81`, `Community 87`, `Community 109`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Grading Tests & Settings` to `Persistence & API Dependencies`, `Community 66`, `Community 67`, `LiteLLM Grading Engine`, `LLM Catalog & Settings`, `Google Classroom Provider`, `Community 37`, `Schemas & Privacy Audit`, `Community 39`, `Community 38`, `Community 34`, `Grading Router & Job Snapshots`, `Community 109`, `Community 84`, `Provider Sessions & Cache Logging`, `Community 87`, `Navigation Rail & Theme`, `Community 58`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `schemas` connect `Community 45` to `Community 70`, `Community 73`, `Community 43`, `Community 47`, `Community 49`, `Privacy Redaction (PII)`, `Community 54`, `Community 55`, `Community 59`, `Community 60`, `Community 61`, `Community 62`, `Community 63`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Are the 94 inferred relationships involving `TestClient` (e.g. with `GradingAiAttempt` and `GradingCriterion`) actually correct?**
  _`TestClient` has 94 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `GradingJob` (e.g. with `GoogleProvider` and `GradingJob`) actually correct?**
  _`GradingJob` has 27 INFERRED edges - model-reasoned connections that need verification._
- **What connects `schema_version`, `default_model`, `enabled` to the rest of the system?**
  _509 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Grading Domain & DB Models` be split into smaller, more focused modules?**
  _Cohesion score 0.09195402298850575 - nodes in this community are weakly interconnected._