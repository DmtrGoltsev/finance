import { describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { registerServiceWorker } from "./registerServiceWorker";

describe("registerServiceWorker", () => {
  it("registers the worker under the Vite base path", () => {
    let loadHandler: (() => void) | undefined;
    const register = vi.fn(async () => ({} as ServiceWorkerRegistration));

    registerServiceWorker({
      isProd: true,
      baseUrl: "/finance/",
      serviceWorker: { register },
      windowRef: {
        isSecureContext: true,
        location: new URL("https://example.test/finance/") as unknown as Location,
        addEventListener: (_event: string, handler: EventListenerOrEventListenerObject) => {
          loadHandler = handler as () => void;
        }
      }
    });

    expect(register).not.toHaveBeenCalled();
    loadHandler?.();

    expect(register).toHaveBeenCalledWith("https://example.test/finance/sw.js", {
      scope: "https://example.test/finance/"
    });
  });

  it("does not register outside production mode", () => {
    const register = vi.fn(async () => ({} as ServiceWorkerRegistration));

    registerServiceWorker({
      isProd: false,
      baseUrl: "/finance/",
      serviceWorker: { register },
      windowRef: {
        isSecureContext: true,
        location: new URL("https://example.test/finance/") as unknown as Location,
        addEventListener: vi.fn() as unknown as Window["addEventListener"]
      }
    });

    expect(register).not.toHaveBeenCalled();
  });

  it("skips registration on plain HTTP IP origins", () => {
    const register = vi.fn(async () => ({} as ServiceWorkerRegistration));

    registerServiceWorker({
      isProd: true,
      baseUrl: "/finance/",
      serviceWorker: { register },
      windowRef: {
        isSecureContext: false,
        location: new URL("http://192.168.1.20/finance/") as unknown as Location,
        addEventListener: vi.fn() as unknown as Window["addEventListener"]
      }
    });

    expect(register).not.toHaveBeenCalled();
  });

  it("does not surface a rejected registration as an app crash", async () => {
    let loadHandler: (() => void) | undefined;
    const register = vi.fn(async () => {
      throw new Error("registration rejected");
    });

    registerServiceWorker({
      isProd: true,
      baseUrl: "/finance/",
      serviceWorker: { register },
      windowRef: {
        isSecureContext: true,
        location: new URL("https://example.test/finance/") as unknown as Location,
        addEventListener: (_event: string, handler: EventListenerOrEventListenerObject) => {
          loadHandler = handler as () => void;
        }
      }
    });

    expect(() => loadHandler?.()).not.toThrow();
    await Promise.resolve();
  });

  it("ships update-safe network-first navigation without caching API or OCR", () => {
    const source = readFileSync("public/sw.js", "utf8");
    const workerContext = {
      URL,
      self: {
        registration: { scope: "https://example.test/finance/" },
        addEventListener: vi.fn(),
        clients: { claim: vi.fn() },
        skipWaiting: vi.fn()
      }
    } as Record<string, unknown>;
    runInNewContext(source, workerContext);
    const isApiOrOcrRequest = workerContext.isApiOrOcrRequest as (url: URL) => boolean;

    expect(source).toContain('const CACHE_NAME = `${CACHE_PREFIX}v3`');
    expect(source).toContain("networkFirst(event.request)");
    expect(source).toContain("self.skipWaiting()");
    expect(source).toContain("self.clients.claim()");
    expect(source).toContain("key.startsWith(CACHE_PREFIX)");
    expect(source).toContain("isApiOrOcrRequest(url)");
    expect(source).toMatch(/\/ocr/);
    expect(isApiOrOcrRequest(new URL("https://example.test/finance/index.html"))).toBe(false);
    expect(isApiOrOcrRequest(new URL("https://example.test/finance-api/api/v1/accounts"))).toBe(true);
    expect(isApiOrOcrRequest(new URL("https://example.test/finance/api/v1/accounts"))).toBe(true);
    expect(isApiOrOcrRequest(new URL("https://example.test/finance/ocr/upload"))).toBe(true);
  });
});
