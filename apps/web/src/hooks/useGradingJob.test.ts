import { describe, expect, it } from "vitest";

import type { GradingSubmission } from "../types";
import { mergeDraftSubmission } from "./useGradingJob";

const baseSubmission: GradingSubmission = {
  id: "sub-1",
  student_email: null,
  student_name: "Ana",
  source_file_id: "file-1",
  source_name: "work.txt",
  mime_type: "text/plain",
  files: [],
  ai_score: 80,
  confidence: 0.9,
  final_score: 90,
  feedback: "Reviewed feedback",
  reviewed: true,
  flag: null,
  error: null,
  error_retryable: false,
  classroom_submission_id: null,
  privacy_status: null,
  extraction_status: null,
  ai_attempt_status: "succeeded",
  ai_engine: null,
  ai_model: null,
  ai_safe_error: null,
  ai_flags: [],
  privacy_flags: [],
  alternate_link: null,
  posted_to_classroom: false,
  posted_at: null,
};

describe("mergeDraftSubmission", () => {
  it("does not downgrade an already reviewed submission when a late draft arrives", () => {
    const lateDraft: GradingSubmission = {
      ...baseSubmission,
      ai_score: 70,
      final_score: 70,
      feedback: "Late draft feedback",
      reviewed: false,
    };

    const merged = mergeDraftSubmission([baseSubmission], lateDraft);

    expect(merged).toHaveLength(1);
    expect(merged[0]).toMatchObject({
      id: "sub-1",
      reviewed: true,
      final_score: 90,
      feedback: "Reviewed feedback",
    });
  });
});
