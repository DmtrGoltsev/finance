import { describe, expect, it } from "vitest";
import {
  buildFinanceWebManifest,
  buildScopedUrl,
  normalizeBasePath
} from "./pwaPaths";

describe("PWA path helpers", () => {
  it("normalizes Vite base paths for root and sub-path deploys", () => {
    expect(normalizeBasePath(undefined)).toBe("/");
    expect(normalizeBasePath("finance")).toBe("/finance/");
    expect(normalizeBasePath("/finance")).toBe("/finance/");
    expect(normalizeBasePath("/finance/")).toBe("/finance/");
  });

  it("builds a scoped manifest for /finance/", () => {
    const manifest = buildFinanceWebManifest("/finance/");

    expect(manifest.start_url).toBe("/finance/");
    expect(manifest.scope).toBe("/finance/");
    expect(manifest.icons[0].src).toBe("/finance/pwa-icon.svg");
    expect(JSON.stringify(manifest)).not.toContain('"scope":"/"');
    expect(JSON.stringify(manifest)).not.toContain('"start_url":"/"');
  });

  it("keeps root deploys valid for local preview", () => {
    expect(buildScopedUrl("/", "sw.js")).toBe("/sw.js");
    expect(buildFinanceWebManifest("/").scope).toBe("/");
  });
});
