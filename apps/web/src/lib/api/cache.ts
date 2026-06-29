import type { CacheEntry } from "./types";

export const responseCache = new Map<string, CacheEntry<unknown>>();
export const inFlight = new Map<string, Promise<unknown>>();
const connectivityListeners = new Set<(offline: boolean) => void>();
const versionSkewListeners = new Set<(skewed: boolean) => void>();
let revalidationFailures = 0;
let offline = false;
let versionSkewNotified = false;

export function subscribeConnectivity(listener: (offline: boolean) => void): () => void {
  connectivityListeners.add(listener);
  listener(offline);
  return () => connectivityListeners.delete(listener);
}

export function subscribeVersionSkew(listener: (skewed: boolean) => void): () => void {
  versionSkewListeners.add(listener);
  listener(versionSkewNotified);
  return () => versionSkewListeners.delete(listener);
}

function setOffline(nextOffline: boolean) {
  if (offline === nextOffline) return;
  offline = nextOffline;
  for (const listener of connectivityListeners) listener(offline);
}

export function markConnectivitySuccess() {
  revalidationFailures = 0;
  setOffline(false);
}

export function markConnectivityFailure() {
  revalidationFailures += 1;
  if (revalidationFailures >= 1) setOffline(true);
}

export function checkAppVersion(response: Response) {
  const serverVersion = response.headers.get("X-App-Version");
  if (!serverVersion || serverVersion === __APP_VERSION__ || versionSkewNotified) return;
  versionSkewNotified = true;
  for (const listener of versionSkewListeners) listener(true);
}

export function cacheKey(path: string) {
  return `GET ${path}`;
}

export function clearApiCache(prefix?: string) {
  for (const key of responseCache.keys()) {
    if (!prefix || key.startsWith(prefix)) responseCache.delete(key);
  }
  for (const key of inFlight.keys()) {
    if (!prefix || key.startsWith(prefix)) inFlight.delete(key);
  }
}
