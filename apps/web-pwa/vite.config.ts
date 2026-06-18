import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { buildFinanceWebManifest, normalizeBasePath } from "./src/pwaPaths";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const basePath = normalizeBasePath(
    env.VITE_BASE_PATH ?? env.FINANCE_PWA_BASE_PATH
  );
  const manifestSource = `${JSON.stringify(buildFinanceWebManifest(basePath), null, 2)}\n`;
  const manifestUrls = new Set([
    "/manifest.webmanifest",
    `${basePath}manifest.webmanifest`
  ]);

  return {
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
    }
  };
});
