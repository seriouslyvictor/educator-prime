export type CacheOptions = {
  cacheKey?: string;
  ttlMs?: number;
  staleMs?: number;
  force?: boolean;
};

export type CacheEntry<T> = {
  value: T;
  freshUntil: number;
  staleUntil: number;
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string | undefined,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function apiErrorFromUnknown(caught: unknown, fallback: string): ApiError {
  if (caught instanceof ApiError) return caught;
  if (caught instanceof Error) return new ApiError(0, undefined, caught.message || fallback);
  return new ApiError(0, undefined, fallback);
}
