import { describe, expect, it } from "vitest";
import { cn } from "./utils";

describe("cn", () => {
  it("merges class names", () => {
    const includeB = false;

    expect(cn("a", "b")).toContain("a");
    expect(cn("a", includeB && "b", "c")).not.toContain("false");
  });
});
