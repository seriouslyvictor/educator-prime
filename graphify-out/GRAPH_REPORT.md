# Graph Report - .  (2026-06-07)

## Corpus Check
- Corpus is ~43,781 words - fits in a single context window. You may not need a graph.

## Summary
- 996 nodes · 3942 edges · 60 communities (50 shown, 10 thin omitted)
- Extraction: 60% EXTRACTED · 40% INFERRED · 0% AMBIGUOUS · INFERRED: 1558 edges (avg confidence: 0.51)
- Token cost: 304,577 input · 0 output

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

## God Nodes (most connected - your core abstractions)
1. `log_event()` - 87 edges
2. `get_settings()` - 80 edges
3. `GradingStatus` - 75 edges
4. `GradingSubmission` - 71 edges
5. `GradingJob` - 70 edges
6. `GoogleProvider` - 68 edges
7. `Session` - 61 edges
8. `GradingEngine` - 58 edges
9. `GradingFileCache` - 56 edges
10. `ExportStatus` - 55 edges

## Surprising Connections (you probably didn't know these)
- `README (Classroom Downloader project overview)` --references--> `Manual Classroom Posting (API limitation)`  [INFERRED]
  README.md → apps/web/src/components/grader/GraderWrap.tsx
- `README (Classroom Downloader project overview)` --references--> `Privacy Audit Gate (AI sees no student data until audit passes)`  [EXTRACTED]
  README.md → apps/web/src/components/grader/GraderSetup.tsx
- `MockGoogleProvider` --semantically_similar_to--> `MockGradingEngine`  [INFERRED] [semantically similar]
  apps/api/src/classroom_downloader/google_provider.py → apps/api/src/classroom_downloader/grading_engine.py
- `test_safe_source_label_does_not_preserve_drive_id_suffix()` --calls--> `extract_submission_content()`  [EXTRACTED]
  apps/api/tests/test_grading.py → apps/api/src/classroom_downloader/content_extraction.py
- `test_safe_source_label_does_not_preserve_identifier_like_suffixes()` --calls--> `extract_submission_content()`  [EXTRACTED]
  apps/api/tests/test_grading.py → apps/api/src/classroom_downloader/content_extraction.py

## Import Cycles
- 1-file cycle: `apps/api/src/classroom_downloader/main.py -> apps/api/src/classroom_downloader/main.py`
- 1-file cycle: `apps/api/src/classroom_downloader/grading.py -> apps/api/src/classroom_downloader/grading.py`
- 1-file cycle: `apps/api/src/classroom_downloader/google_provider.py -> apps/api/src/classroom_downloader/google_provider.py`

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

## Communities (60 total, 10 thin omitted)

### Community 0 - "Core Grading Pipeline"
Cohesion: 0.11
Nodes (99): GradingFileCache, datetime, ExtractedSubmissionContent, GoogleProvider, GradingEngine, GradingFileCache, GradingJob, GradingJobRead (+91 more)

### Community 1 - "API Routes & Job Management"
Cohesion: 0.26
Nodes (82): Activity, datetime, GoogleProvider, GradingEngine, GradingJob, GradingJobRead, Path, PrivacyAuditRead (+74 more)

### Community 2 - "LLM Grading Engine"
Cohesion: 0.07
Nodes (49): Any, GradingEngineRequest, LlmModelEntry, GradingEngineRequest, LlmModelEntry, get_grading_engine(), GradingEngineResult, GradingReadiness (+41 more)

### Community 3 - "Privacy Audit System"
Cohesion: 0.08
Nodes (48): GoogleProvider, GradingJob, GradingSubmission, PrivacyAuditRead, Session, SubmissionFile, delete_job_cache(), Classroom Downloader API. (+40 more)

### Community 4 - "Frontend Navigation UI"
Cohesion: 0.07
Nodes (26): ConnectView(), InlineError(), DoneView(), DryRunDrawer(), AppIcon(), IconName, icons, ProgressLogItem (+18 more)

### Community 5 - "Test Fixtures & Settings"
Cohesion: 0.07
Nodes (40): get_settings(), Multi-file Submission Grouping, _CapturingEngine (grading test double), _enable_litellm_engine helper, _seed_infer_job helper, _seed_preview_cache helper, test_brief_mode_sends_rubric_text_and_keeps_default_criteria(), test_classroom_links_endpoint_backfills_links_and_posted_state() (+32 more)

### Community 6 - "LLM Model Catalog"
Cohesion: 0.12
Nodes (37): Any, Path, Settings, Path, Settings, BaseSettings, _bool_or_none(), _cache_is_stale() (+29 more)

### Community 7 - "UI Component Library"
Cohesion: 0.08
Nodes (32): Card(), CardContent(), CardDescription(), CardFooter(), CardHeader(), CardTitle(), cn(), RadioGroup() (+24 more)

### Community 8 - "Grader Review Panel"
Cohesion: 0.09
Nodes (26): BlockedEvidence, BlockedEvidence(), extensionOf(), GraderReview(), hasDefaultCriteria(), initials(), INLINE_IMAGE_MIME, INLINE_TEXT_EXTENSIONS (+18 more)

### Community 9 - "Frontend API & Caching"
Cohesion: 0.09
Nodes (29): Stale-While-Revalidate API Cache Pattern, privacyTone, api, CacheEntry, cacheKey(), CacheOptions, clearApiCache(), fetchJson() (+21 more)

### Community 10 - "Google Classroom API"
Cohesion: 0.11
Nodes (16): ClassroomActivity, ClassroomCourse, FakeClassroomService (test double), FakeCourses (test double), FakeDriveService (test double), FakeClassroomService, FakeCourses, FakeCourseWork (+8 more)

### Community 11 - "Google Drive Integration"
Cohesion: 0.15
Nodes (10): drive_files_from_submission(), _due_label(), get_google_provider(), GoogleApiProvider, MockGoogleProvider, submission_links_from_submission(), SubmissionLink, byte_preview() (+2 more)

### Community 12 - "UI History & Icons"
Cohesion: 0.11
Nodes (20): AppIcon, HistoryView(), EmptyState(), SearchBox(), SkeletonRows(), ReferenceQueueCard(), referenceQueueStatus(), referenceQueueStatus (+12 more)

### Community 13 - "Database & Migrations"
Cohesion: 0.12
Nodes (17): Session, _ensure_activity_columns(), _ensure_cache_columns(), _ensure_columns(), _ensure_grading_ai_attempt_columns(), _ensure_grading_criterion_columns(), _ensure_grading_job_columns(), _ensure_grading_submission_columns() (+9 more)

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
Cohesion: 0.19
Nodes (13): Any, _bounded_repr(), _bounded_text(), configure_logging(), _format_event(), _format_value(), JsonEventFormatter, log_debug() (+5 more)

### Community 18 - "Google Auth & Profile"
Cohesion: 0.30
Nodes (11): datetime, AccountProfile, _cache_hit(), _ttl(), _TtlCacheEntry, get_logger(), log_cache_hit(), log_cache_miss() (+3 more)

### Community 19 - "Grader Workflow UI"
Cohesion: 0.15
Nodes (10): Manual Classroom Posting (API limitation), GraderQueue(), GraderTopbar(), GraderWrap(), postingClipboardText(), scoreOf(), scoreOf, studentLabel (+2 more)

### Community 20 - "Grading Test Doubles"
Cohesion: 0.27
Nodes (12): _CapturingEngine, _infer_provider(), _seed_infer_job(), test_grade_loop_no_longer_swaps_criteria(), test_infer_caps_sample_at_configured_size(), test_infer_falls_back_to_defaults_when_no_signal(), test_infer_mode_replaces_defaults_with_ai_criteria(), test_infer_uses_description_only_when_substantial() (+4 more)

### Community 21 - "OAuth Token Management"
Cohesion: 0.31
Nodes (11): get_google_provider(), auth_me(), create_export(), google_auth_http_exception(), _is_fresh(), list_activities(), list_courses(), prepare_classroom_links() (+3 more)

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
Cohesion: 0.33
Nodes (3): clear_google_provider_caches(), Shared pytest configuration for the API test suite.  Two isolation concerns ar, _reset_global_state()

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
Cohesion: 0.40
Nodes (4): _looks_like_user_id(), A bare numeric Google account id leaking in as a display name (e.g. when a, test_drive_files_carry_classroom_submission_id_for_grouping(), test_looks_like_user_id_only_flags_bare_numeric_ids()

### Community 39 - "Browser File System Types"
Cohesion: 0.40
Nodes (4): FileSystemDirectoryHandle, FileSystemFileHandle, FileSystemWritableFileStream, Window

### Community 40 - "OAuth Auth URL"
Cohesion: 0.67
Nodes (3): build_oauth_authorization_url(), auth_start(), test_build_oauth_authorization_url_uses_configured_web_client()

### Community 42 - "File Preview Tests"
Cohesion: 0.67
Nodes (3): _seed_preview_cache(), test_preview_binary_still_attachment(), test_preview_code_file_served_inline_as_text_plain()

## Knowledge Gaps
- **142 isolated node(s):** `allow`, `schema_version`, `default_model`, `enabled`, `display_name` (+137 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Teacher-Loop Modes (off/approve/auto/cowrite)` connect `UI Component Library` to `Grader Review Panel`, `Test Fixtures & Settings`?**
  _High betweenness centrality (0.165) - this node is a cross-community bridge._
- **Why does `Student Pseudonymization before AI` connect `Privacy & PII Protection` to `Grader Review Panel`, `Logging & Observability`, `LLM Grading Engine`, `Test Fixtures & Settings`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Why does `Settings` connect `LLM Model Catalog` to `DeepSeek Model Config`, `Logging & Observability`, `LLM Grading Engine`, `Test Fixtures & Settings`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Are the 70 inferred relationships involving `GradingStatus` (e.g. with `Activity` and `datetime`) actually correct?**
  _`GradingStatus` has 70 INFERRED edges - model-reasoned connections that need verification._
- **Are the 64 inferred relationships involving `GradingSubmission` (e.g. with `Activity` and `datetime`) actually correct?**
  _`GradingSubmission` has 64 INFERRED edges - model-reasoned connections that need verification._
- **Are the 64 inferred relationships involving `GradingJob` (e.g. with `Activity` and `datetime`) actually correct?**
  _`GradingJob` has 64 INFERRED edges - model-reasoned connections that need verification._
- **What connects `allow`, `schema_version`, `default_model` to the rest of the system?**
  _169 weakly-connected nodes found - possible documentation gaps or missing edges._