import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      globals: true,
      include: ["src/**/*.test.{ts,tsx}"],
      coverage: {
        provider: "v8",
        include: ["src/lib/**", "src/components/grader/**"],
      },
    },
  }),
);
