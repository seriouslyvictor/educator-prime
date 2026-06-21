import { useEffect, useState } from "react";

import {
  ApiError,
  api,
  apiErrorFromUnknown,
  subscribeConnectivity,
  subscribeVersionSkew,
} from "../lib/api";
import type { AppView, AuthState, GradingHealth } from "../types";

const classroomScopes = [
  "openid",
  "email",
  "profile",
  "https://www.googleapis.com/auth/classroom.courses.readonly",
  "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
  "https://www.googleapis.com/auth/classroom.rosters.readonly",
  "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
  "https://www.googleapis.com/auth/classroom.profile.emails",
  "https://www.googleapis.com/auth/classroom.profile.photos",
  "https://www.googleapis.com/auth/drive.readonly",
];

type UseConnectionOptions = {
  setView: (view: AppView) => void;
  setBusy: (busy: boolean) => void;
  setError: (error: ApiError | string | null) => void;
  loadCourses: () => Promise<void>;
  loadGradingQueue: () => Promise<void>;
  restoreGradingJob: (jobId: string) => Promise<boolean>;
  readStoredJobId: () => string | null;
  resetWorkspace: () => void;
};


function readGoogleCallbackError(): ApiError | null {
  const params = new URLSearchParams(window.location.search);
  const googleStatus = params.get("google");
  const googleReason = params.get("reason");
  if (googleStatus !== "error" || !googleReason) return null;
  window.history.replaceState({}, "", window.location.pathname);
  return new ApiError(401, googleReason, "Google sign-in did not complete.");
}

function appError(caught: unknown, fallback: string): ApiError {
  return apiErrorFromUnknown(caught, fallback);
}

export function useConnection({
  setView,
  setBusy,
  setError,
  loadCourses,
  loadGradingQueue,
  restoreGradingJob,
  readStoredJobId,
  resetWorkspace,
}: UseConnectionOptions) {
  const [auth, setAuth] = useState<AuthState | null>(null);
  const [googleCallbackError] = useState<ApiError | null>(() => readGoogleCallbackError());
  const [loading, setLoading] = useState(true);
  const [apiOffline, setApiOffline] = useState(false);
  const [versionSkew, setVersionSkew] = useState(false);
  const [gradingHealth, setGradingHealth] = useState<GradingHealth | null>(null);

  const connected = Boolean(auth?.signed_in && auth.classroom_scopes && auth.drive_scopes);
  const partialConsent = Boolean(
    auth?.signed_in && (!auth.classroom_scopes || !auth.drive_scopes),
  );

  async function bootstrap() {
    setLoading(true);
    setError(null);
    if (googleCallbackError) {
      setAuth(null);
      setError(googleCallbackError);
      setView("connect");
      setLoading(false);
      return;
    }
    try {
      const authState = await api.authMe();
      setAuth(authState);
      const hasConnection = authState.signed_in && authState.classroom_scopes && authState.drive_scopes;
      if (!hasConnection) {
        setView("connect");
        return;
      }
      void api.gradingHealth().then(setGradingHealth).catch(() => setGradingHealth(null));
      try {
        await loadCourses();
      } catch (caught) {
        setError(appError(caught, "Falha ao carregar o estado do app."));
        setView("connect");
        return;
      }
      await loadGradingQueue();
      const restoredJobId = readStoredJobId();
      if (restoredJobId && (await restoreGradingJob(restoredJobId))) {
        return;
      }
      setView("workspace");
    } catch (caught) {
      setAuth(null);
      setError(appError(caught, "Falha ao carregar o estado da conexao."));
      setView("connect");
    } finally {
      setLoading(false);
    }
  }

  async function connectClassroom() {
    setBusy(true);
    setError(null);
    try {
      const authStart = await api.connectGoogle(classroomScopes);
      if (authStart.authorization_url) {
        window.location.href = authStart.authorization_url;
        return;
      }
      await bootstrap();
    } catch (caught) {
      setError(appError(caught, "Falha ao conectar o Google."));
    } finally {
      setBusy(false);
    }
  }

  async function logoutClassroom() {
    setBusy(true);
    setError(null);
    try {
      const nextAuth = await api.logoutGoogle();
      setAuth(nextAuth);
      resetWorkspace();
      setView("connect");
    } catch (caught) {
      setError(appError(caught, "Falha ao sair da conta Google."));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => subscribeConnectivity(setApiOffline), []);

  useEffect(() => subscribeVersionSkew(setVersionSkew), []);

  return {
    auth,
    loading,
    apiOffline,
    versionSkew,
    gradingHealth,
    connected,
    partialConsent,
    bootstrap,
    connectClassroom,
    logoutClassroom,
  };
}
