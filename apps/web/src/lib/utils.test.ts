import { describe, expect, it } from "vitest";
import { cn } from "./utils";

describe("cn", () => {
  it("joins truthy class names and drops falsy ones", () => {
    const includeB = false;

    expect(cn("a", includeB && "b", "c")).toBe("a c");
  });

  it("merges conflicting Tailwind utility classes, keeping the last one", () => {
    expect(cn("p-2", "p-4")).toMatch(/p-4$/);
  });
});
