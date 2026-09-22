import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // The browser only ever talks to /api; the backend holds the LLM key.
  server: { proxy: { "/api": process.env.API_URL || "http://localhost:8000" }, allowedHosts: true },
  test: { environment: "jsdom", setupFiles: "./src/setup.js", globals: true },
});
