import react from "@vitejs/plugin-react";
import { fixturePreview } from "./preview/server";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => ({
  root: import.meta.dirname,
  plugins: [react(), ...(mode === "preview" ? [fixturePreview()] : [])],
  build: {
    outDir: mode === "preview" ? "dist-preview" : "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
    exclude: ["e2e/**", "node_modules/**", "dist/**", "dist-preview/**"],
  },
}));
