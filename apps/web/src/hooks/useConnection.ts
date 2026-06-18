import { useEffect, useState } from "react";

import {
  ApiError,
  api,
  apiErrorFromUnknown,
  subscribeConnectivity,
  subscribeVersionSkew,
} from "../lib/api";
import type { AppView, AuthState, GradingHealth } from "../types";

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
  const [loading, setLoading] = useState(true);
  const [apiOffline, setApiOffline] = useState(false);
  const [versionSkew, setVersionSkew] = useState(false);
  const [gradingHealth, setGradingHealth] = useState<GradingHealth | null>(null);

  const signedIn = Boolean(auth?.signed_in && auth.identity_scopes);
  const classroomReady = Boolean(auth?.classroom_scopes);
  const driveReady = Boolean(auth?.drive_scopes);
  const connected = Boolean(signedIn && classroomReady);
  const partialConsent = Boolean(
    signedIn && !classroomReady,
  );

  async function bootstrap() {
    setLoading(true);
    setError(null);
    try {
      const authState = await api.authMe();
      setAuth(authState);
      const hasIdentity = authState.signed_in && authState.identity_scopes;
      if (!hasIdentity) {
        setView("connect");
        return;
      }
      if (!authState.classroom_scopes) {
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
    } catch {
      setAuth(null);
      setView("connect");
    } finally {
      setLoading(false);
    }
  }

  async function requestGoogleCapability(
    capability: "identity" | "classroom_read" | "drive_read",
    reason: string,
  ) {
    setBusy(true);
    setError(null);
    try {
      const authStart = await api.connectGoogle(capability, reason);
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

  async function connectIdentity() {
    await requestGoogleCapability(
      "identity",
      "Entrar no Classroom Downloader com sua conta Google escolar.",
    );
  }

  async function connectClassroomRead() {
    await requestGoogleCapability(
      "classroom_read",
      "Listar suas turmas e atividades do Google Classroom.",
    );
  }

  async function connectDriveRead() {
    await requestGoogleCapability(
      "drive_read",
      "Baixar os arquivos anexados nas entregas escolhidas.",
    );
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
    signedIn,
    classroomReady,
    driveReady,
    partialConsent,
    bootstrap,
    connectIdentity,
    connectClassroomRead,
    connectDriveRead,
    connectClassroom: connectIdentity,
    logoutClassroom,
  };
}
