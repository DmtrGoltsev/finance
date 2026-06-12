import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.codex.finance",
  appName: "Finance",
  webDir: "dist",
  server: {
    url: "http://45.10.110.42/finance/",
    cleartext: true
  }
};

export default config;
