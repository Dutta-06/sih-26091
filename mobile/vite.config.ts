import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  base: "./", // assets load from the Android WebView's local file server
  plugins: [react(), tailwindcss()],
  build: { target: "es2020", assetsInlineLimit: 0 },
  test: { environment: "node", setupFiles: ["src/test/openData.setup.ts"] },
});
