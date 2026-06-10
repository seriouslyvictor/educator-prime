import json, classroom_downloader.grading as g

REQUIRED = [
    # routers/grading.py
    "_criteria_match_defaults", "_replace_job_criteria", "default_cache_expiry",
    "delete_job_cache", "draft_grading_job", "ensure_default_criteria", "grading_csv",
    "grading_job_snapshot", "infer_job_criteria", "retry_submission",
    # privacy_audit.py
    "_submission_for_file", "cache_submission_file", "scrub_submission_cached",
    # api/deps.py + tests
    "get_grading_engine", "group_key_for", "DEFAULT_CRITERIA", "_draft_submission",
    "grading_submission_snapshot", "CachedScrubbedSubmission",
]
missing = [n for n in REQUIRED if not hasattr(g, n)]
assert not missing, f"missing from public surface: {missing}"
assert callable(g.get_grading_engine), "get_grading_engine patch point broken"
assert getattr(g, "litellm", None) is not None, "litellm patch point missing"
print(json.dumps({"required_surface": sorted(REQUIRED), "ok": True}, indent=2))
