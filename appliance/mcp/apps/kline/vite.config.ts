import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { viteSingleFile } from "vite-plugin-singlefile";
import { defineConfig } from "vitest/config";

const root = dirname(fileURLToPath(import.meta.url));
const outputHtml = resolve(root, "../../qmt_mcp_apps/resources/kline-chart-v1.html");

export default defineConfig({
  plugins: [
    viteSingleFile(),
    {
      name: "normalize-single-file-html",
      closeBundle() {
        const html = readFileSync(outputHtml, "utf8");
        writeFileSync(outputHtml, html.replace(/[ \t]+$/gm, ""), "utf8");
      },
    },
  ],
  server: {
    host: "0.0.0.0",
    allowedHosts: ["terminal.local", "localhost", "127.0.0.1"],
  },
  build: {
    target: "es2022",
    outDir: resolve(root, "../../qmt_mcp_apps/resources"),
    emptyOutDir: false,
    cssCodeSplit: false,
    assetsInlineLimit: 100_000_000,
    rollupOptions: {
      input: resolve(root, "kline-chart-v1.html"),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
