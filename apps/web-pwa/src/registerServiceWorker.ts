import { buildScopedUrl, normalizeBasePath } from "./pwaPaths";

type ServiceWorkerContainerLike = {
  register(scriptURL: string | URL, options?: RegistrationOptions): Promise<ServiceWorkerRegistration>;
};

type RegisterServiceWorkerOptions = {
  isProd?: boolean;
  baseUrl?: string;
  serviceWorker?: ServiceWorkerContainerLike;
  windowRef?: Pick<Window, "addEventListener" | "isSecureContext" | "location">;
};

export function registerServiceWorker(options: RegisterServiceWorkerOptions = {}) {
  const isProd = options.isProd ?? import.meta.env.PROD;
  const serviceWorker =
    options.serviceWorker ??
    (typeof navigator === "undefined" ? undefined : navigator.serviceWorker);
  const windowRef = options.windowRef ?? (typeof window === "undefined" ? undefined : window);

  if (!isProd || !serviceWorker || !windowRef) {
    return;
  }

  if (!canUseServiceWorker(windowRef)) {
    return;
  }

  const baseUrl = normalizeBasePath(options.baseUrl ?? import.meta.env.BASE_URL);
  const scope = new URL(baseUrl, windowRef.location.origin).toString();
  const swUrl = new URL(buildScopedUrl(baseUrl, "sw.js"), windowRef.location.origin).toString();

  windowRef.addEventListener("load", () => {
    void serviceWorker.register(swUrl, { scope }).catch(() => {
      // Plain HTTP IP origins cannot register service workers; the app stays usable.
    });
  });
}

function canUseServiceWorker(windowRef: Pick<Window, "isSecureContext" | "location">): boolean {
  if (windowRef.isSecureContext) {
    return true;
  }

  const hostname = windowRef.location.hostname;
  return windowRef.location.protocol === "http:" && (hostname === "localhost" || hostname === "127.0.0.1");
}
