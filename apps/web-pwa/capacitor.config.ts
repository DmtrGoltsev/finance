import type { CapacitorConfig } from "@capacitor/cli";

const serverUrl = requireHttpsUrl("CAPACITOR_SERVER_URL", process.env.CAPACITOR_SERVER_URL);

const config: CapacitorConfig = {
  appId: "com.codex.finance",
  appName: "Finance",
  webDir: "dist",
  server: {
    url: serverUrl
  }
};

export default config;

function requireHttpsUrl(name: string, value: string | undefined): string {
  const candidate = value?.trim();
  if (!candidate) {
    throw new Error(`${name} must be set to an HTTPS URL for the legacy Capacitor wrapper.`);
  }
  const parsed = new URL(candidate);
  if (parsed.protocol !== "https:") {
    throw new Error(`${name} must use HTTPS; refusing cleartext production configuration.`);
  }
  return parsed.toString();
}
