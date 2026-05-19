import { describe, expect, it, vi } from "vitest";
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
});
