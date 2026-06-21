import { ApiError } from "@/lib/api";
import { Gate, OfflinePill } from "@/components/errors";
import { InlineError } from "@/components/ui";
import { Skeleton } from "@/components/ui/skeleton";
import { resolveAuthStage } from "./authState";
import { AuthExplainer } from "./AuthExplainer";
import { LoginScreen } from "./LoginScreen";
import { PermissionStage } from "./PermissionStage";
import type { AuthState, Course } from "@/types";

export function AuthGate({
  auth,
  loading,
  busy,
  courses,
  error,
  partialConsent,
  apiOffline,
  versionSkew,
  onConnect,
  onLogout,
  onRetry,
}: {
  auth: AuthState | null;
  loading: boolean;
  busy: boolean;
  courses: Course[];
  error: unknown;
  partialConsent: boolean;
  apiOffline: boolean;
  versionSkew: boolean;
  onConnect: () => void;
  onLogout: () => void;
  onRetry: () => void;
}) {
  const stage = resolveAuthStage({ auth, loading, courses, error, partialConsent });

  if (stage.kind === "ready") return null;

  return (
    <div data-auth-stage={stage.kind}>
      {versionSkew ? (
        <InlineError
          error={new ApiError(0, "version_skew", "Frontend and backend versions differ.")}
          onAction={() => window.location.reload()}
        />
      ) : null}
      {stage.kind === "booting" ? (
        <div className="grid min-h-screen gap-6 bg-background p-8 lg:grid-cols-[1fr_440px]">
          <div className="flex flex-col justify-between gap-8">
            <Skeleton className="h-10 w-64" />
            <div className="flex flex-col gap-4">
              <Skeleton className="h-12 w-full max-w-2xl" />
              <Skeleton className="h-12 w-full max-w-xl" />
              <Skeleton className="h-6 w-full max-w-lg" />
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <Skeleton className="h-28" />
              <Skeleton className="h-28" />
              <Skeleton className="h-28" />
            </div>
          </div>
          <Skeleton className="min-h-[420px]" />
        </div>
      ) : stage.kind === "signin" ? (
        <LoginScreen connecting={busy} onConnect={onConnect} />
      ) : stage.kind === "grant-classroom" ? (
        <PermissionStage
          auth={auth}
          busy={busy}
          capability="classroom"
          partialConsent={stage.partialConsent}
          onGrant={onConnect}
          onLogout={onLogout}
        />
      ) : stage.kind === "grant-drive" ? (
        <PermissionStage
          auth={auth}
          busy={busy}
          capability="drive"
          partialConsent={stage.partialConsent}
          onGrant={onConnect}
          onLogout={onLogout}
        />
      ) : stage.kind === "no-courses" ? (
        <AuthExplainer stage="no-courses" auth={auth} onLogout={onLogout} />
      ) : stage.kind === "classroom-unavailable" ? (
        <AuthExplainer stage="classroom-unavailable" auth={auth} onLogout={onLogout} />
      ) : stage.kind === "policy-blocked" ? (
        <AuthExplainer stage="policy-blocked" auth={auth} onLogout={onLogout} />
      ) : (
        <Gate error={stage.error} onAction={onRetry} />
      )}
      {apiOffline ? <OfflinePill /> : null}
    </div>
  );
}
