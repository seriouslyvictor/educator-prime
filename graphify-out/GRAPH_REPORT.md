# Graph Report - Classroom Downloader  (2026-06-12)

## Corpus Check
- 137 files · ~71,528 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1840 nodes · 4694 edges · 111 communities (105 shown, 6 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 557 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `773a6569`
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
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 104|Community 104]]
- [[_COMMUNITY_Community 105|Community 105]]
- [[_COMMUNITY_Community 109|Community 109]]
- [[_COMMUNITY_Community 113|Community 113]]
- [[_COMMUNITY_Community 115|Community 115]]
- [[_COMMUNITY_Community 116|Community 116]]

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
- 1-file cycle: `apps/api/src/classroom_downloader/routers/admin.py -> apps/api/src/classroom_downloader/routers/admin.py`
- 1-file cycle: `apps/api/src/classroom_downloader/grading/_common.py -> apps/api/src/classroom_downloader/grading/_common.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/health.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/admin.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/deps.py`
- 2-file cycle: `apps/api/src/classroom_downloader/api/errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/api/errors.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/main.py`
- 2-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/main.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/auth.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/courses.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/exports.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/common.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/api/common.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/auth_errors.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/api/auth_errors.py`
- 3-file cycle: `apps/api/src/classroom_downloader/api/deps.py -> apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/routers/grading.py -> apps/api/src/classroom_downloader/api/deps.py`

## Hyperedges (group relationships)
- **api/ Support Layer (common, auth_errors, session_cleanup, deps)** — plan_api_common, plan_api_auth_errors, plan_api_session_cleanup, plan_api_deps [EXTRACTED 0.90]
- **Domain Routers by Bounded Context** — plan_routers_health, plan_routers_auth, plan_routers_courses, plan_routers_exports, plan_routers_grading [EXTRACTED 0.90]
- **One-Way Import Chain (main to routers to deps to api-support to services)** — plan_compat_reexports, plan_routers_grading, plan_api_deps, plan_api_session_cleanup, plan_api_auth_errors [EXTRACTED 0.85]

## Communities (111 total, 6 thin omitted)

### Community 0 - "Grading Domain & DB Models"
Cohesion: 0.09
Nodes (16): AttemptFilters, AttemptSheet(), EventFilters, EventSheet(), formatCost(), formatDate(), prettyJson(), shortId() (+8 more)

### Community 1 - "Persistence & API Dependencies"
Cohesion: 0.21
Nodes (24): ExtractedSubmissionContent, GoogleProvider, GradingEngine, GradingFileCache, GradingJob, GradingSubmission, Session, SubmissionFile (+16 more)

### Community 2 - "Grading Tests & Settings"
Cohesion: 0.10
Nodes (56): get_settings(), TestClient, _seed_preview_cache(), _sse_payloads(), test_brief_mode_sends_rubric_text_and_keeps_default_criteria(), test_classroom_links_endpoint_backfills_links_and_posted_state(), test_create_job_exposes_visual_submission_consent(), test_create_job_persists_teacher_criteria() (+48 more)

### Community 3 - "Grading Router & Job Snapshots"
Cohesion: 0.11
Nodes (48): GradingJob, Session, GradingJob, GradingJobRead, Session, GoogleProvider, GradingEngine, GradingJob (+40 more)

### Community 4 - "LiteLLM Grading Engine"
Cohesion: 0.05
Nodes (84): Path, Any, GradingEngineRequest, LlmModelEntry, VisionExtractionResult, Path, GradingEngineRequest, LlmModelEntry (+76 more)

### Community 5 - "LLM Catalog & Settings"
Cohesion: 0.14
Nodes (34): Any, Path, Settings, Path, Settings, BaseSettings, _bool_or_none(), _cache_is_stale() (+26 more)

### Community 6 - "Google Classroom Provider"
Cohesion: 0.33
Nodes (6): _enable_litellm_engine(), Point settings at a local single-model catalog with litellm selected.     conft, test_draft_returns_503_when_provider_key_missing(), test_grading_health_ready_when_provider_key_present(), test_grading_health_reports_missing_provider_key(), test_grading_health_reports_model_not_enabled()

### Community 7 - "LLM Model Overrides Config"
Cohesion: 0.05
Nodes (38): display_name, enabled, notes, rpm_limit, tpm_limit, use_cases, default_model, display_name (+30 more)

### Community 8 - "Schemas & Privacy Audit"
Cohesion: 0.50
Nodes (4): required, title, type, ExportFileRead

### Community 9 - "Auth Flow & Token Store"
Cohesion: 0.12
Nodes (42): GradingFileCache, Path, Path, GradingFileCache, Path, _decode_text(), extract_submission_content(), _is_zip_submission() (+34 more)

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
Cohesion: 0.05
Nodes (42): Any, AccountProfile, _cache_hit(), ClassroomActivity, ClassroomCourse, drive_files_from_submission(), _due_label(), GoogleApiProvider (+34 more)

### Community 19 - "TypeScript Config"
Cohesion: 0.09
Nodes (21): compilerOptions, allowJs, allowSyntheticDefaultImports, baseUrl, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx (+13 more)

### Community 20 - "Privacy Redaction (PII)"
Cohesion: 0.08
Nodes (26): properties, format, title, type, title, type, anyOf, title (+18 more)

### Community 21 - "Provider Sessions & Cache Logging"
Cohesion: 0.50
Nodes (4): required, title, type, GradingFileCacheRead

### Community 22 - "Observability & Logging"
Cohesion: 0.08
Nodes (59): AdminStats, AiAttemptAdminRead, AiAttemptPayloadRead, Session, AppEvent, datetime, Session, GoogleProvider (+51 more)

### Community 23 - "Grader Shell (UI)"
Cohesion: 0.67
Nodes (3): title, type, content_hash

### Community 24 - "Navigation Rail & Theme"
Cohesion: 0.16
Nodes (21): GoogleProvider, GradingCriterion, GradingEngine, GradingJob, Session, _collect_inference_samples(), infer_job_criteria(), Reuse the audit's cached + scrubbed content to build a privacy-safe sample. (+13 more)

### Community 25 - "Grading Resume Tests"
Cohesion: 0.39
Nodes (7): _create_job(), Coverage for the resume/preview additions: the global grading-jobs list and the, test_jobs_list_collapses_to_newest_per_activity(), test_jobs_list_surfaces_created_job(), test_submission_preview_forces_download_for_unsafe_type(), test_submission_preview_streams_image_inline(), test_submission_preview_unknown_job_is_404()

### Community 26 - "Courses Router"
Cohesion: 0.12
Nodes (17): title, type, title, type, properties, anyOf, title, detail (+9 more)

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
Cohesion: 0.12
Nodes (25): _as_utc(), _cache_headers(), _conditional_response(), _etag(), _if_none_match(), _is_fresh(), _is_future(), SSE + generic HTTP-cache primitives.  No domain dependencies. (+17 more)

### Community 35 - "Community 35"
Cohesion: 0.15
Nodes (14): init_db(), test_auth_me_profile_failure_keeps_loadable_google_token_signed_in(), test_course_cache_logs_standard_hit_miss_pair(), test_courses_exclude_archived(), test_courses_reports_expired_google_session_as_unauthorized(), test_export_creates_email_first_manifest_paths(), test_file_content_stream_uses_private_etag_cache(), test_file_content_streams() (+6 more)

### Community 36 - "Community 36"
Cohesion: 0.17
Nodes (31): Session + provider + filesystem cache purge (side-effectful)., GradingAiAttempt, GradingSubmission, GradingSubmissionFile, Path, GradingJob, GradingSubmission, GradingJob (+23 more)

### Community 37 - "Community 37"
Cohesion: 0.67
Nodes (3): anyOf, title, deleted_at

### Community 38 - "Community 38"
Cohesion: 0.12
Nodes (30): _as_utc(), FastAPI dependencies: session, user, provider, grading engine., Google API transient-error classification., datetime, datetime, GradingCriterion, Session, Session (+22 more)

### Community 39 - "Community 39"
Cohesion: 0.36
Nodes (13): GradingAiAttempt, GradingJob, GradingSubmission, Session, Session, _record_attempt(), _clear_rows(), DummyEngine (+5 more)

### Community 40 - "Community 40"
Cohesion: 0.11
Nodes (19): title, type, anyOf, title, anyOf, title, anyOf, title (+11 more)

### Community 41 - "Community 41"
Cohesion: 0.37
Nodes (18): GoogleProvider, GradingJob, GradingSubmission, PrivacyAuditRead, Session, SubmissionFile, GoogleProvider, SubmissionFile (+10 more)

### Community 42 - "Community 42"
Cohesion: 0.67
Nodes (3): anyOf, title, error

### Community 43 - "Community 43"
Cohesion: 0.11
Nodes (19): type, properties, required, title, type, title, type, title (+11 more)

### Community 44 - "Community 44"
Cohesion: 0.67
Nodes (3): title, type, mime_type

### Community 45 - "Community 45"
Cohesion: 0.09
Nodes (22): required, title, type, required, title, type, required, title (+14 more)

### Community 46 - "Community 46"
Cohesion: 0.14
Nodes (14): title, type, title, type, properties, completed_files, course_name, status (+6 more)

### Community 47 - "Community 47"
Cohesion: 0.12
Nodes (17): properties, required, title, type, anyOf, title, due_label, state (+9 more)

### Community 48 - "Community 48"
Cohesion: 0.17
Nodes (11): cn(), InputGroup(), InputGroupAddon(), inputGroupAddonVariants, InputGroupButton(), inputGroupButtonVariants, InputGroupInput(), Input() (+3 more)

### Community 49 - "Community 49"
Cohesion: 0.12
Nodes (19): anyOf, title, properties, properties, required, title, type, anyOf (+11 more)

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
Cohesion: 0.09
Nodes (23): properties, title, type, title, type, anyOf, title, title (+15 more)

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
Cohesion: 0.20
Nodes (10): title, type, anyOf, title, properties, activity_name, export_mime_type, source_name (+2 more)

### Community 62 - "Community 62"
Cohesion: 0.20
Nodes (10): title, type, title, type, properties, byte_size, expires_at, submission_id (+2 more)

### Community 63 - "Community 63"
Cohesion: 0.22
Nodes (9): anyOf, title, type, properties, required, title, type, criteria (+1 more)

### Community 64 - "Community 64"
Cohesion: 0.14
Nodes (14): properties, anyOf, title, anyOf, title, anyOf, title, cache_write_tokens (+6 more)

### Community 65 - "Community 65"
Cohesion: 0.25
Nodes (18): ExtractedSubmissionContent, GradingJob, GradingSubmission, Session, _extract_zip_content(), ExtractedSubmissionContent, GradingPseudonym, text_preview() (+10 more)

### Community 66 - "Community 66"
Cohesion: 0.07
Nodes (42): Exception, Path, Request, AppEvent, _ensure_activity_columns(), _ensure_cache_columns(), _ensure_columns(), _ensure_grading_ai_attempt_columns() (+34 more)

### Community 67 - "Community 67"
Cohesion: 0.14
Nodes (15): AuthStart, build_oauth_authorization_url(), clear_google_provider_caches(), get_google_provider(), Legacy single-user helper. Use make_google_provider() for multi-user flows., TokenStore, log_event(), log_warning() (+7 more)

### Community 68 - "Community 68"
Cohesion: 0.15
Nodes (6): Field(), FieldGroup(), FieldLabel(), fieldVariants, Label(), Separator()

### Community 69 - "Community 69"
Cohesion: 0.67
Nodes (3): title, type, output_path

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
Cohesion: 0.17
Nodes (12): anyOf, title, properties, required, title, type, default, title (+4 more)

### Community 74 - "Community 74"
Cohesion: 0.21
Nodes (13): _contains_invalid_grant(), google_auth_http_exception(), _http_403_is_hard_auth_failure(), _http_error_content(), Google auth-error → HTTP translation.  Pure, no side effects., Build the grading engine, translating config failures (missing key /     disabl, resolve_grading_engine(), api_error() (+5 more)

### Community 75 - "Community 75"
Cohesion: 0.18
Nodes (6): Select(), SelectContent(), SelectGroup(), SelectItem(), SelectTrigger(), SelectValue()

### Community 76 - "Community 76"
Cohesion: 0.67
Nodes (3): source_file_id, title, type

### Community 77 - "Community 77"
Cohesion: 0.20
Nodes (10): type, default, items, title, type, missing_keys, scopes, items (+2 more)

### Community 78 - "Community 78"
Cohesion: 0.67
Nodes (3): student_email, anyOf, title

### Community 79 - "Community 79"
Cohesion: 0.36
Nodes (6): Card(), CardContent(), CardDescription(), CardFooter(), CardHeader(), CardTitle()

### Community 80 - "Community 80"
Cohesion: 0.67
Nodes (3): student_name, anyOf, title

### Community 81 - "Community 81"
Cohesion: 0.26
Nodes (14): GradingJob, GradingSubmission, GradingSubmissionFile, Session, SubmissionFile, ensure_submission_file(), _group_files(), group_key_for() (+6 more)

### Community 82 - "Community 82"
Cohesion: 0.14
Nodes (14): title, type, properties, required, title, type, activity_id, rubric_mode (+6 more)

### Community 83 - "Community 83"
Cohesion: 0.17
Nodes (12): items, default, items, title, type, default, items, title (+4 more)

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
Cohesion: 0.24
Nodes (11): Activity, google_api_http_exception(), Exception, HTTPException, GoogleProvider, Session, UserSession, Course (+3 more)

### Community 88 - "Community 88"
Cohesion: 0.40
Nodes (5): Tabs(), TabsContent(), TabsList(), tabsListVariants, TabsTrigger()

### Community 89 - "Community 89"
Cohesion: 0.50
Nodes (4): default, title, type, batch_mode

### Community 90 - "Community 90"
Cohesion: 0.50
Nodes (4): required, title, type, ExportJobRead

### Community 91 - "Community 91"
Cohesion: 0.50
Nodes (4): required, title, type, GradingCriterionInput

### Community 92 - "Community 92"
Cohesion: 0.50
Nodes (4): default, title, type, has_payload

### Community 93 - "Community 93"
Cohesion: 0.50
Nodes (4): default, title, type, include_visual_submissions

### Community 94 - "Community 94"
Cohesion: 0.50
Nodes (4): retry_count, default, title, type

### Community 95 - "Community 95"
Cohesion: 0.50
Nodes (4): default, title, type, probed

### Community 96 - "Community 96"
Cohesion: 0.50
Nodes (4): teacher_loop, default, title, type

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

### Community 104 - "Community 104"
Cohesion: 0.67
Nodes (3): token_count, anyOf, title

### Community 109 - "Community 109"
Cohesion: 0.10
Nodes (31): AuthFailure, admin_email_set(), get_current_session(), get_current_user_email(), is_admin_email(), provider_dependency(), require_admin(), purge_cached_classroom_state_for_user() (+23 more)

### Community 115 - "Community 115"
Cohesion: 0.67
Nodes (3): title, type, job_id

### Community 116 - "Community 116"
Cohesion: 0.67
Nodes (3): anyOf, title, model

## Knowledge Gaps
- **463 isolated node(s):** `schema_version`, `default_model`, `enabled`, `display_name`, `use_cases` (+458 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `log_event()` connect `Community 67` to `Community 65`, `Community 66`, `Persistence & API Dependencies`, `LiteLLM Grading Engine`, `LLM Catalog & Settings`, `Community 38`, `Community 39`, `Grading Router & Job Snapshots`, `Auth Flow & Token Store`, `Community 41`, `Community 34`, `Community 109`, `Community 81`, `Exports Router & File Naming`, `Observability & Logging`, `Community 87`, `Navigation Rail & Theme`, `Community 58`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Grading Tests & Settings` to `Community 65`, `Community 66`, `Community 67`, `Community 36`, `LiteLLM Grading Engine`, `Community 38`, `LLM Catalog & Settings`, `Community 39`, `Persistence & API Dependencies`, `Grading Router & Job Snapshots`, `Google Classroom Provider`, `Community 109`, `Exports Router & File Naming`, `Community 84`, `Observability & Logging`, `Navigation Rail & Theme`, `Community 58`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `schemas` connect `Community 45` to `Community 70`, `Schemas & Privacy Audit`, `Community 73`, `Community 91`, `Community 43`, `Community 40`, `Community 47`, `Community 49`, `Community 82`, `Provider Sessions & Cache Logging`, `Community 54`, `Community 90`, `Community 59`, `Community 60`, `Community 63`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Are the 94 inferred relationships involving `TestClient` (e.g. with `GradingAiAttempt` and `GradingCriterion`) actually correct?**
  _`TestClient` has 94 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `GradingJob` (e.g. with `GoogleProvider` and `GradingJob`) actually correct?**
  _`GradingJob` has 27 INFERRED edges - model-reasoned connections that need verification._
- **What connects `schema_version`, `default_model`, `enabled` to the rest of the system?**
  _509 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Grading Domain & DB Models` be split into smaller, more focused modules?**
  _Cohesion score 0.09195402298850575 - nodes in this community are weakly interconnected._