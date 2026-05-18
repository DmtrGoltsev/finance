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
        location: new URL("https://example.test/finance/") as unknown as Location,
        addEventListener: vi.fn() as unknown as Window["addEventListener"]
      }
    });

    expect(register).not.toHaveBeenCalled();
  });
});
