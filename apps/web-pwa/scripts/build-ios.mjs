import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const packageRoot = path.resolve(scriptDir, "..");
const apiBaseUrl = requireHttpsUrl(
  "CAPACITOR_API_BASE_URL",
  process.env.CAPACITOR_API_BASE_URL ?? process.env.VITE_API_BASE_URL,
);
requireHttpsUrl("CAPACITOR_SERVER_URL", process.env.CAPACITOR_SERVER_URL);

const iosEnv = {
  ...process.env,
  VITE_BASE_PATH: "/",
  VITE_API_BASE_URL: apiBaseUrl,
};

function requireHttpsUrl(name, value) {
  const candidate = value?.trim();
  if (!candidate) {
    console.error(`${name} must be set to an HTTPS URL for the legacy Capacitor build.`);
    process.exit(1);
  }
  let parsed;
  try {
    parsed = new URL(candidate);
  } catch {
    console.error(`${name} must be a valid HTTPS URL.`);
    process.exit(1);
  }
  if (parsed.protocol !== "https:") {
    console.error(`${name} must use HTTPS; refusing cleartext production configuration.`);
    process.exit(1);
  }
  return parsed.toString().replace(/\/$/, "");
}

function run(args) {
  const result = spawnSync(process.execPath, args, {
    cwd: packageRoot,
    env: iosEnv,
    stdio: "inherit",
  });

  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

console.log("Building iOS web assets with VITE_BASE_PATH=/");
console.log(`Building iOS web assets with VITE_API_BASE_URL=${apiBaseUrl}`);

run(["./node_modules/typescript/bin/tsc", "-b"]);
run(["./node_modules/vite/bin/vite.js", "build"]);
