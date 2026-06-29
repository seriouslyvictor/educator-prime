/**
 * Public API client facade.
 *
 * Implementation is split across lib/api/:
 *   types.ts   – shared types and ApiError
 *   cache.ts   – response cache, in-flight dedup, connectivity/version-skew state
 *   client.ts  – request<T> and fetchJson transport
 *   auth.ts    – authentication endpoints
 *   courses.ts – courses, activities, and export endpoints
 *   grading.ts – grading job endpoints
 *   admin.ts   – admin/monitoring endpoints
 *
 * All callers should continue to import from this file unchanged.
 */

export { ApiError, apiErrorFromUnknown } from "./api/types";
export { subscribeConnectivity, subscribeVersionSkew } from "./api/cache";

import { admin } from "./api/admin";
import { auth } from "./api/auth";
import { courses } from "./api/courses";
import { grading } from "./api/grading";

export const api = {
  ...admin,
  ...auth,
  ...courses,
  ...grading,
};
