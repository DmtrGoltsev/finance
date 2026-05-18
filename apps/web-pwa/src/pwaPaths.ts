export type FinanceWebManifest = {
  name: string;
  short_name: string;
  description: string;
  start_url: string;
  scope: string;
  display: "standalone";
  background_color: string;
  theme_color: string;
  lang: string;
  icons: Array<{
    src: string;
    sizes: string;
    type: string;
    purpose: string;
  }>;
};

export function normalizeBasePath(value: string | undefined): string {
  const trimmed = value?.trim() || "/";
  const withLeadingSlash = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  const withTrailingSlash = withLeadingSlash.endsWith("/")
    ? withLeadingSlash
    : `${withLeadingSlash}/`;
  return withTrailingSlash.replace(/\/{2,}/g, "/");
}

export function buildScopedUrl(basePath: string, assetPath: string): string {
  return `${normalizeBasePath(basePath)}${assetPath.replace(/^\/+/, "")}`;
}

export function buildFinanceWebManifest(basePath: string): FinanceWebManifest {
  const normalizedBasePath = normalizeBasePath(basePath);

  return {
    name: "Финансы MVP",
    short_name: "Финансы",
    description: "PWA панель семейных финансов для ручного MVP учета",
    start_url: normalizedBasePath,
    scope: normalizedBasePath,
    display: "standalone",
    background_color: "#f7f8fb",
    theme_color: "#f7f8fb",
    lang: "ru",
    icons: [
      {
        src: buildScopedUrl(normalizedBasePath, "pwa-icon.svg"),
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any maskable"
      }
    ]
  };
}
