import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import type { AuthState, Course } from "@/types";
import { resolveAuthStage } from "./authState";

const signedOut: AuthState = {
  signed_in: false,
  identity_scopes: false,
  classroom_scopes: false,
  drive_scopes: false,
  email: null,
  name: null,
  picture: null,
  provider: "google",
};

const signedIn = (overrides: Partial<AuthState> = {}): AuthState => ({
  signed_in: true,
  identity_scopes: true,
  classroom_scopes: true,
  drive_scopes: true,
  email: "teacher@example.com",
  name: "Teacher",
  picture: null,
  provider: "google",
  ...overrides,
});

const course: Course = {
  id: "course-1",
  name: "Turma A",
  section: null,
  course_state: "ACTIVE",
};

function stage(input: Parameters<typeof resolveAuthStage>[0]) {
  return resolveAuthStage(input).kind;
}

describe("resolveAuthStage", () => {
  it("renders booting while bootstrap is loading", () => {
    expect(stage({ auth: null, loading: true, courses: [], error: null })).toBe("booting");
  });

  it("renders signin when signed out", () => {
    expect(stage({ auth: signedOut, loading: false, courses: [], error: null })).toBe("signin");
  });

  it("asks for Classroom scopes after identity", () => {
    const result = resolveAuthStage({
      auth: signedIn({ classroom_scopes: false, drive_scopes: false }),
      loading: false,
      courses: [],
      error: null,
    });
    expect(result).toEqual({ kind: "grant-classroom", partialConsent: false });
  });

  it("marks partial consent when Classroom remains unchecked after an attempt", () => {
    const result = resolveAuthStage({
      auth: signedIn({ classroom_scopes: false }),
      loading: false,
      courses: [],
      error: null,
      partialConsent: true,
    });
    expect(result).toEqual({ kind: "grant-classroom", partialConsent: true });
  });

  it("asks for Drive after Classroom is ready", () => {
    expect(
      stage({
        auth: signedIn({ drive_scopes: false }),
        loading: false,
        courses: [],
        error: null,
      }),
    ).toBe("grant-drive");
  });

  it("leaves the gate when connected with courses", () => {
    expect(stage({ auth: signedIn(), loading: false, courses: [course], error: null })).toBe("ready");
  });

  it("shows a no-Classroom explainer for connected accounts with no courses", () => {
    expect(stage({ auth: signedIn(), loading: false, courses: [], error: null })).toBe("no-courses");
  });

  it("shows the Classroom unavailable explainer", () => {
    expect(
      stage({
        auth: signedIn(),
        loading: false,
        courses: [],
        error: new ApiError(403, "classroom_not_available", "No Classroom"),
      }),
    ).toBe("classroom-unavailable");
  });

  it("shows consent denied as a gate error", () => {
    expect(
      stage({
        auth: null,
        loading: false,
        courses: [],
        error: new ApiError(401, "google_auth_denied", "Denied"),
      }),
    ).toBe("gate");
  });

  it("shows org policy as a dedicated explainer", () => {
    expect(
      stage({
        auth: null,
        loading: false,
        courses: [],
        error: new ApiError(401, "google_policy_blocked", "Blocked"),
      }),
    ).toBe("policy-blocked");
  });

  it("handles oauth not configured, expired Google sessions, offline, and banners", () => {
    expect(stage({ auth: null, loading: false, courses: [], error: new ApiError(503, "oauth_not_configured", "Missing") })).toBe("gate");
    expect(stage({ auth: null, loading: false, courses: [], error: new ApiError(401, "google_session_expired", "Expired") })).toBe("gate");
    expect(stage({ auth: null, loading: false, courses: [], error: new ApiError(0, "unreachable", "Offline") })).toBe("gate");
    expect(stage({ auth: signedIn(), loading: false, courses: [course], error: new ApiError(503, "google_rate_limited", "Slow") })).toBe("ready");
    expect(stage({ auth: signedIn(), loading: false, courses: [course], error: new ApiError(0, "version_skew", "Skew") })).toBe("ready");
  });
});
