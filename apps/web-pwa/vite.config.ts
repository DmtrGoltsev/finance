import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { buildFinanceWebManifest, normalizeBasePath } from "./src/pwaPaths";

const basePath = normalizeBasePath(
  process.env.VITE_BASE_PATH ?? process.env.FINANCE_PWA_BASE_PATH
);
const manifestSource = `${JSON.stringify(buildFinanceWebManifest(basePath), null, 2)}\n`;
const manifestUrls = new Set([
  "/manifest.webmanifest",
  `${basePath}manifest.webmanifest`
]);

export default defineConfig({
  base: basePath,
  plugins: [
    react(),
    {
      name: "finance-pwa-manifest",
      configureServer(server) {
        server.middlewares.use((request, response, next) => {
          const requestPath = request.url?.split("?")[0] ?? "";
          if (!manifestUrls.has(requestPath)) {
            next();
            return;
          }

          response.setHeader("Content-Type", "application/manifest+json");
          response.end(manifestSource);
        });
      },
      generateBundle() {
        this.emitFile({
          type: "asset",
          fileName: "manifest.webmanifest",
          source: manifestSource
        });
      }
    }
  ],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./vitest.setup.ts"
  },
});
