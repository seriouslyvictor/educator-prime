import { ApiError } from "@/lib/api";
import type { AuthState, Course } from "@/types";

export type AuthStage =
  | { kind: "booting" }
  | { kind: "signin" }
  | { kind: "grant-classroom"; partialConsent: boolean }
  | { kind: "grant-drive"; partialConsent: boolean }
  | { kind: "no-courses" }
  | { kind: "classroom-unavailable"; error: ApiError }
  | { kind: "policy-blocked"; error: ApiError }
  | { kind: "gate"; error: unknown }
  | { kind: "ready" };

type ResolveAuthStageInput = {
  auth: AuthState | null;
  loading: boolean;
  courses: Course[];
  error: unknown;
  partialConsent?: boolean;
};

function apiCode(error: unknown): string | undefined {
  return error instanceof ApiError ? error.code : undefined;
}

export function resolveAuthStage({
  auth,
  loading,
  courses,
  error,
  partialConsent = false,
}: ResolveAuthStageInput): AuthStage {
  if (loading) return { kind: "booting" };

  const code = apiCode(error);
  if (error) {
    if (code === "classroom_not_available" && error instanceof ApiError) {
      return { kind: "classroom-unavailable", error };
    }
    if (code === "google_policy_blocked" && error instanceof ApiError) {
      return { kind: "policy-blocked", error };
    }
    if (
      code === "google_auth_denied" ||
      code === "oauth_not_configured" ||
      code === "google_session_expired" ||
      code === "unreachable"
    ) {
      return { kind: "gate", error };
    }
  }

  if (!auth?.signed_in) return { kind: "signin" };
  if (!auth.classroom_scopes) return { kind: "grant-classroom", partialConsent };
  if (!auth.drive_scopes) return { kind: "grant-drive", partialConsent };
  if (courses.length === 0) return { kind: "no-courses" };
  return { kind: "ready" };
}
