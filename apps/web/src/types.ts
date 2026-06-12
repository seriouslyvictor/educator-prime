export interface AuthState {
  signed_in: boolean;
  identity_scopes: boolean;
  classroom_scopes: boolean;
  drive_scopes: boolean;
  email: string | null;
  name: string | null;
  picture: string | null;
  provider: string;
  is_admin?: boolean;
}

export interface GradingHealth {
  engine: string;
  ready: boolean;
  status: "ok" | "mock" | "model_not_enabled" | "provider_key_missing" | "unknown_engine";
  model: string | null;
  provider: string | null;
  missing_keys: string[];
  detail: string;
  probed: boolean;
  probe_ok: boolean | null;
}

export interface Course {
  id: string;
  name: string;
  section: string | null;
  course_state: string;
}

export interface Activity {
  id: string;
  course_id: string;
  title: string;
  work_type: string;
  state: string;
  due_label: string | null;
}

export interface ExportFile {
  id: string;
  activity_id: string;
  activity_name: string;
  student_email: string | null;
  student_name: string | null;
  source_name: string;
  mime_type: string;
  export_mime_type: string | null;
  output_path: string;
  status: string;
  error: string | null;
}

export interface ExportJob {
  id: string;
  course_id: string;
  course_name: string;
  status: "queued" | "running" | "completed" | "failed";
  total_files: number;
  completed_files: number;
  files: ExportFile[];
  errors: Array<{ id: string; message: string; file_id: string | null }>;
}

export type GradingStatus = "ready" | "drafting" | "reviewing" | "completed";
export type QueueState = "active" | "archived" | "hidden";
export type QueueAction = "restart" | "remove" | "archive" | "hide" | "restore";

export interface GradingQueueItem {
  course_id: string;
  course_name: string;
  activity_id: string;
  activity_title: string;
  due_label: string | null;
  submission_count: number;
  status: GradingStatus | "ready";
  latest_job_id: string | null;
  queue_state: QueueState;
  reviewed_submissions: number;
  total_submissions: number;
}

export interface GradingCriterion {
  id: string;
  name: string;
  weight: number;
  description: string | null;
  latest_ai_note: string | null;
}

export interface GradingCriterionInput {
  name: string;
  weight: number;
  description?: string | null;
}

export interface GradingSubmissionFile {
  source_file_id: string;
  source_name: string;
  mime_type: string;
}

export interface GradingSubmission {
  id: string;
  student_email: string | null;
  student_name: string | null;
  source_file_id: string;
  source_name: string;
  mime_type: string;
  files: GradingSubmissionFile[];
  ai_score: number | null;
  confidence: number | null;
  final_score: number | null;
  feedback: string | null;
  reviewed: boolean;
  flag: string | null;
  error: string | null;
  classroom_submission_id: string | null;
  alternate_link: string | null;
  posted_to_classroom: boolean;
  posted_at: string | null;
  privacy_status: string | null;
  extraction_status: string | null;
  ai_attempt_status: string | null;
  error_retryable: boolean;
  ai_engine: string | null;
  ai_model: string | null;
  ai_safe_error: string | null;
  ai_flags: string[];
  privacy_flags: string[];
  ai_prompt_tokens?: number | null;
  ai_completion_tokens?: number | null;
  ai_token_count?: number | null;
  ai_cached_prompt_tokens?: number | null;
  ai_cache_write_tokens?: number | null;
  ai_cost_cents?: number | null;
  ai_latency_ms?: number | null;
}

export interface GradingFileCache {
  id: string;
  submission_id: string;
  source_file_id: string;
  source_name: string;
  mime_type: string;
  content_hash: string;
  byte_size: number;
  expires_at: string;
  deleted_at: string | null;
}

export interface GradingJob {
  id: string;
  course_id: string;
  course_name: string;
  activity_id: string;
  activity_title: string;
  rubric_mode: string;
  teacher_loop: string;
  rubric_text: string | null;
  include_visual_submissions: boolean;
  queue_state: QueueState;
  status: GradingStatus;
  total_submissions: number;
  reviewed_submissions: number;
  flagged_submissions: number;
  cache_expires_at: string | null;
  criteria: GradingCriterion[];
  submissions: GradingSubmission[];
  cache_files: GradingFileCache[];
}

export interface PrivacyAuditRow {
  id: string;
  submission_id: string;
  student_label: string;
  redacted_source_name: string;
  mime_type: string;
  byte_size: number;
  extraction_status: string;
  extraction_error: string | null;
  privacy_status: string;
  privacy_flags: string[];
  redaction_counts: Record<string, number>;
  remaining_direct_identifier_hits: string[];
  audit_pass: boolean;
  blocked_reason: string | null;
}

export interface PrivacyAudit {
  id: string;
  job_id: string;
  status: string;
  total_files: number;
  passed_files: number;
  redacted_files: number;
  blocked_files: number;
  high_risk_files: number;
  created_at: string;
  updated_at: string;
  rows: PrivacyAuditRow[];
}

export type RubricMode = "infer" | "brief" | "structured" | "saved" | "calibrate";

export type TeacherLoopMode = "auto" | "approve" | "cowrite" | "off";

export type AppView =
  | "admin"
  | "connect"
  | "workspace"
  | "progress"
  | "done"
  | "history"
  | "graderQueue"
  | "graderSetup"
  | "graderReview"
  | "graderWrap";

export type ThemeMode = "system" | "light" | "dark";

export interface LocalExportHistoryItem {
  id: string;
  courseName: string;
  activityCount: number;
  fileCount: number;
  failedFiles?: Array<{ path: string; reason: string }>;
  completedAt: string;
  outputLabel: string;
}

export interface AppEventItem {
  id: string;
  created_at: string;
  level: string;
  event: string;
  logger_name: string;
  user_email: string | null;
  request_id: string | null;
  fields_json: string;
  exc_text: string | null;
}

export interface AiAttemptItem {
  id: string;
  job_id: string;
  submission_id: string;
  stage: string;
  engine: string;
  model: string | null;
  status: string;
  extraction_status: string;
  privacy_status: string;
  safe_error: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  token_count: number | null;
  cached_prompt_tokens: number | null;
  cache_write_tokens: number | null;
  cost_cents: number | null;
  latency_ms: number | null;
  retryable: boolean;
  retry_count: number;
  created_at: string;
  has_payload: boolean;
}

export interface AiAttemptPayload {
  attempt_id: string;
  prompt_text: string;
  response_text: string | null;
}

export interface AdminStats {
  events_24h_by_level: Record<string, number>;
  attempts_7d: number;
  failures_7d: number;
  cost_cents_7d: number;
}
