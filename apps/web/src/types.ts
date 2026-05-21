export interface AuthState {
  signed_in: boolean;
  identity_scopes: boolean;
  classroom_scopes: boolean;
  drive_scopes: boolean;
  email: string | null;
  name: string | null;
  picture: string | null;
  provider: string;
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

export type AppView = "connect" | "workspace" | "progress" | "done" | "history";

export type ThemeMode = "system" | "light" | "dark";

export interface LocalExportHistoryItem {
  id: string;
  courseName: string;
  activityCount: number;
  fileCount: number;
  completedAt: string;
  outputLabel: string;
}
