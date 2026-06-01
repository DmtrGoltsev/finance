import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const packageRoot = path.resolve(scriptDir, "..");

const iosEnv = {
  ...process.env,
  VITE_BASE_PATH: "/",
  VITE_API_BASE_URL: "http://45.10.110.42/finance-api",
};

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
console.log("Building iOS web assets with VITE_API_BASE_URL=http://45.10.110.42/finance-api");

run(["./node_modules/typescript/bin/tsc", "-b"]);
run(["./node_modules/vite/bin/vite.js", "build"]);
