import { beforeEach, describe, expect, it, vi } from "vitest";
import { LiveFinanceApiClient, getApiBaseUrl } from "./client";

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body
  } as Response;
}

describe("LiveFinanceApiClient", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    document.cookie = "finance_csrf=; Max-Age=0; path=/";
  });

  it("uses the production Finance API prefix when no explicit API base is set", () => {
    vi.stubEnv("PROD", true);
    vi.stubEnv("VITE_API_BASE_URL", "");

    expect(getApiBaseUrl()).toBe("/finance-api");
  });

  it("normalizes an explicit API base without breaking sub-path deploys", () => {
    vi.stubEnv("PROD", true);
    vi.stubEnv("VITE_API_BASE_URL", "/finance-api/");

    expect(getApiBaseUrl()).toBe("/finance-api");
  });

  it("logs in with PWA cookie transport, avoids localStorage tokens, and maps dashboard data", async () => {
    const localStorageGet = vi.spyOn(Storage.prototype, "getItem");
    const localStorageSet = vi.spyOn(Storage.prototype, "setItem");
    const localStorageRemove = vi.spyOn(Storage.prototype, "removeItem");
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      const headers = new Headers(init?.headers);

      expect(init?.credentials).toBe("include");
      expect(headers.get("Authorization")).toBeNull();

      if (path === "/api/v1/sessions" && init?.method === "POST") {
        expect(init.body).toBe(
          JSON.stringify({
            email: "owner@example.test",
            password: "secret-password",
            transport: "pwa_cookie"
          })
        );
        expect(headers.get("X-CSRF-Token")).toBeNull();
        return jsonResponse({
          transport: "pwa_cookie",
          csrfToken: "csrf-1",
          expiresAt: "2026-05-18T10:00:00Z",
          actor: actor()
        }, 201);
      }

      if (path === "/api/v1/sessions/current") {
        return jsonResponse({ actor: actor() });
      }

      if (path === "/api/v1/accounts") {
        return jsonResponse({
          items: [
            {
              id: "account-1",
              name: "Dev Personal Cash",
              accountType: "cash",
              ownershipType: "personal",
              ownerUserId: "user-1",
              householdId: null,
              currency: "USD",
              currentBalance: "925.50"
            }
          ]
        });
      }
      if (path === "/api/v1/categories") {
        return jsonResponse({
          items: [{ id: "category-1", name: "Dev Salary", type: "income" }]
        });
      }
      if (path === "/api/v1/transactions") {
        return jsonResponse({
          items: [
            {
              id: "transaction-1",
              transactionType: "income",
              accountId: "account-1",
              counterpartyAccountId: null,
              categoryId: "category-1",
              amount: "250.00",
              currency: "USD",
              occurredAt: "2026-05-18T08:00:00Z",
              description: "Dev sample income"
            },
            {
              id: "transaction-asset-1",
              transactionType: "asset_buy",
              accountId: "account-1",
              counterpartyAccountId: null,
              categoryId: null,
              amount: "50.00",
              currency: "USD",
              occurredAt: "2026-05-18T09:00:00Z",
              description: null
            }
          ]
        });
      }
      if (path.startsWith("/api/v1/reports/summary?")) {
        const params = new URLSearchParams(path.split("?")[1]);
        return jsonResponse({
          data: {
            reportMode: params.get("reportMode"),
            currency: "USD",
            incomeTotal: "250.00",
            expenseTotal: "69.75",
            netTotal: "180.25"
          }
        });
      }

      throw new Error(`Unexpected request: ${path}`);
    });

    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    await client.loginWithPassword({
      email: "owner@example.test",
      password: "secret-password"
    });
    const snapshot = await client.getDashboardSnapshot();

    expect(localStorageGet).not.toHaveBeenCalled();
    expect(localStorageSet).not.toHaveBeenCalled();
    expect(localStorageRemove).not.toHaveBeenCalled();
    expect(snapshot.session.accessLabel).toBe("Вход выполнен");
    expect(snapshot.session.householdId).toBe("household-1");
    expect(snapshot.accounts[0]).toMatchObject({
      name: "Личные наличные",
      ownerName: "Личное",
      balance: { value: 925.5, currency: "USD" }
    });
    expect(snapshot.categories[0]).toMatchObject({
      name: "Зарплата"
    });
    expect(snapshot.operations[0]).toMatchObject({
      title: "Зарплата",
      amount: { value: 250, currency: "USD" }
    });
    expect(snapshot.operations[1]).toMatchObject({
      title: "Покупка актива",
      amount: { value: 50, currency: "USD" }
    });
    expect(snapshot.reports).toHaveLength(2);
    expect(JSON.stringify(snapshot)).not.toMatch(/\bDev\b/);
  });

  it("reuses an existing cookie session without falling back to login", async () => {
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      expect(init?.credentials).toBe("include");
      expect(new Headers(init?.headers).get("Authorization")).toBeNull();

      if (path === "/api/v1/sessions/current") {
        return jsonResponse({ actor: actor() });
      }
      if (path === "/api/v1/accounts" || path === "/api/v1/categories" || path === "/api/v1/transactions") {
        return jsonResponse({ items: [] });
      }
      if (path.startsWith("/api/v1/reports/summary?")) {
        return jsonResponse({
          data: {
            reportMode: new URLSearchParams(path.split("?")[1]).get("reportMode"),
            currency: "RUB",
            incomeTotal: 0,
            expenseTotal: 0,
            netTotal: 0
          }
        });
      }

      throw new Error(`Unexpected request: ${path}`);
    });

    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    await client.getDashboardSnapshot();

    expect(
      fetcher.mock.calls.some(
        ([url, init]) =>
          String(url) === "http://api.test/api/v1/sessions" &&
          init?.method === "POST"
      )
    ).toBe(false);
  });

  it("does not silently demo-login when the current session is missing", async () => {
    const fetcher = vi.fn(async (url: string | URL | Request, _init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      if (path === "/api/v1/sessions/current") {
        return jsonResponse({ error: { code: "AUTHENTICATION_REQUIRED" } }, 401);
      }

      throw new Error(`Unexpected request: ${path}`);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    await expect(client.getDashboardSnapshot()).rejects.toThrow("failed: 401");
    expect(
      fetcher.mock.calls.some(
        ([url, init]) =>
          String(url) === "http://api.test/api/v1/sessions" &&
          init?.method === "POST"
      )
    ).toBe(false);
  });

  it("sends householdId when creating a shared account", async () => {
    document.cookie = "finance_csrf=csrf-account; path=/";
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      const headers = new Headers(init?.headers);

      expect(path).toBe("/api/v1/accounts");
      expect(init?.method).toBe("POST");
      expect(headers.get("X-CSRF-Token")).toBe("csrf-account");
      expect(init?.body).toBe(
        JSON.stringify({
          name: "Family Wallet",
          accountType: "bank",
          ownershipType: "shared",
          householdId: "household-1",
          currency: "RUB",
          initialBalance: "100"
        })
      );

      return jsonResponse({
        data: {
          id: "account-new",
          name: "Family Wallet",
          accountType: "bank",
          ownershipType: "shared",
          ownerUserId: null,
          householdId: "household-1",
          currency: "RUB",
          currentBalance: "100.00",
          status: "active",
          version: 1
        }
      });
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const account = await client.createDemoAccount({
      name: "Family Wallet",
      kind: "bank",
      currency: "RUB",
      initialBalance: 100,
      ownershipType: "shared",
      householdId: "household-1"
    });

    expect(account.householdId).toBe("household-1");
  });

  it("creates and updates category payload fields supported by the API", async () => {
    document.cookie = "finance_csrf=csrf-category; path=/";
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      const headers = new Headers(init?.headers);
      expect(headers.get("X-CSRF-Token")).toBe("csrf-category");

      if (path === "/api/v1/categories" && init?.method === "POST") {
        expect(init?.body).toBe(
          JSON.stringify({
            name: "Подработка",
            type: "income",
            scope: "household",
            householdId: "household-1",
            iconKey: "income",
            color: "#087f5b"
          })
        );
        return jsonResponse({
          data: categoryDto({
            id: "category-new",
            name: "Подработка",
            type: "income",
            scope: "household",
            householdId: "household-1",
            iconKey: "income",
            color: "#087f5b",
            version: 1
          })
        });
      }

      if (path === "/api/v1/categories/category-new" && init?.method === "PATCH") {
        expect(init?.body).toBe(
          JSON.stringify({
            name: "Подработка новая",
            iconKey: "wallet",
            color: "#2563eb",
            version: 1
          })
        );
        return jsonResponse({
          data: categoryDto({
            id: "category-new",
            name: "Подработка новая",
            type: "income",
            scope: "household",
            householdId: "household-1",
            iconKey: "wallet",
            color: "#2563eb",
            version: 2
          })
        });
      }

      throw new Error(`Unexpected request: ${path}`);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const category = await client.createDemoCategory({
      name: "Подработка",
      direction: "income",
      scope: "household",
      householdId: "household-1",
      iconKey: "income",
      color: "#087f5b"
    });
    const updated = await client.updateCategory({
      categoryId: category.id,
      name: "Подработка новая",
      iconKey: "wallet",
      color: "#2563eb",
      version: category.version
    });

    expect(updated).toMatchObject({
      id: "category-new",
      name: "Подработка новая",
      direction: "income",
      scope: "household",
      householdId: "household-1",
      version: 2
    });
  });

  it("maps the nested live report summary shape", async () => {
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      expect(init?.credentials).toBe("include");

      if (path === "/api/v1/sessions/current") {
        return jsonResponse({ actor: actor() });
      }
      if (path === "/api/v1/accounts") {
        return jsonResponse({
          items: [
            {
              id: "account-1",
              name: "Dev Personal Cash",
              accountType: "cash",
              ownershipType: "personal",
              ownerUserId: "user-1",
              householdId: null,
              currency: "USD",
              currentBalance: "925.50"
            }
          ]
        });
      }
      if (path === "/api/v1/categories" || path === "/api/v1/transactions") {
        return jsonResponse({ items: [] });
      }
      if (path.startsWith("/api/v1/reports/summary?")) {
        const params = new URLSearchParams(path.split("?")[1]);
        return jsonResponse({
          data: {
            scope: { reportMode: params.get("reportMode") },
            totalsByCurrency: [
              {
                currency: "USD",
                incomeTotal: "250.00",
                expenseTotal: "105.75",
                netTotal: "144.25"
              }
            ]
          }
        });
      }

      throw new Error(`Unexpected request: ${path}`);
    });

    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const snapshot = await client.getDashboardSnapshot();

    expect(snapshot.reports[0]).toMatchObject({
      mode: "shared_family_report",
      title: "Общее",
      income: { value: 250, currency: "USD" },
      expense: { value: 105.75, currency: "USD" },
      balanceDelta: { value: 144.25, currency: "USD" }
    });
    expect(snapshot.reports[1]).toMatchObject({
      mode: "combined_viewer_overview",
      title: "Обзор"
    });
  });

  it("requests report preview with file metadata only", async () => {
    document.cookie = "finance_csrf=csrf-import; path=/";
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      const headers = new Headers(init?.headers);

      expect(path).toBe("/api/v1/imports/report-preview");
      expect(init?.method).toBe("POST");
      expect(init?.credentials).toBe("include");
      expect(headers.get("Content-Type")).toBe("application/json");
      expect(headers.get("X-CSRF-Token")).toBe("csrf-import");
      expect(headers.get("Authorization")).toBeNull();
      expect(init?.body).toBe(
        JSON.stringify({
          reportType: "bank_statement",
          sourceType: "file_metadata_only",
          targetScope: "shared",
          householdId: "household-1",
          fileName: "statement.pdf",
          fileSizeBytes: 245760,
          mimeType: "application/pdf"
        })
      );
      expect(String(init?.body)).not.toMatch(/fileContent|base64|parsedData|rows|accountIds/);

      return jsonResponse({
        status: "preview_placeholder",
        canConfirm: false,
        willChangeData: false,
        message: "Файл не импортирован. Сейчас показана только предварительная сводка.",
        scope: { targetScope: "shared", householdId: "household-1" },
        file: {
          fileName: "statement.pdf",
          fileSizeBytes: 245760,
          mimeType: "application/pdf"
        },
        summary: {
          title: "Предварительный просмотр импорта",
          statusText: "Импорт пока не выполняется",
          sections: []
        },
        warnings: [
          {
            code: "NO_DATA_CHANGES_WITHOUT_CONFIRMATION",
            text: "Данные не изменятся без подтверждения."
          },
          {
            code: "NO_FILE_STORAGE_OR_PARSING",
            text: "Содержимое файла не сохраняется и не разбирается."
          },
          {
            code: "PLACEHOLDER_ONLY",
            text: "Импорт пока не выполняется."
          }
        ]
      });
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const preview = await client.previewImportReport({
      reportType: "bank_statement",
      sourceType: "file_metadata_only",
      targetScope: "shared",
      householdId: "household-1",
      fileName: "statement.pdf",
      fileSizeBytes: 245760,
      mimeType: "application/pdf"
    });

    expect(preview).toMatchObject({
      status: "preview_placeholder",
      canConfirm: false,
      willChangeData: false,
      scope: { targetScope: "shared", householdId: "household-1" }
    });
  });

  it("falls back to the report preview placeholder when backend is not ready", async () => {
    const fetcher = vi.fn(async () => jsonResponse({ error: { code: "NOT_FOUND" } }, 404));
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const preview = await client.previewImportReport({
      reportType: "metals_report",
      sourceType: "file_metadata_only",
      targetScope: "personal",
      householdId: "household-1",
      fileName: "metals.xlsx",
      fileSizeBytes: 1024,
      mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    });

    expect(preview).toMatchObject({
      status: "preview_placeholder",
      canConfirm: false,
      willChangeData: false,
      scope: { targetScope: "personal", householdId: null },
      file: { fileName: "metals.xlsx", fileSizeBytes: 1024 },
      summary: { statusText: "Импорт пока не выполняется" }
    });
    expect(preview.summary.sections.map((section) => section.key)).toEqual([
      "accounts_assets",
      "transactions",
      "categories",
      "transfers",
      "brokerage_deposits_metals"
    ]);
    expect(preview.warnings.map((warning) => warning.text)).toContain(
      "Содержимое файла не сохраняется и не разбирается."
    );
    expect(preview.warnings.map((warning) => warning.code)).toContain(
      "NO_FILE_STORAGE_OR_PARSING"
    );
  });

  it("falls back to the report preview placeholder for a missing dev endpoint", async () => {
    const fetcher = vi.fn(async () => jsonResponse({ error: { code: "METHOD_NOT_ALLOWED" } }, 405));
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const preview = await client.previewImportReport({
      reportType: "bank_statement",
      sourceType: "file_metadata_only",
      targetScope: "personal",
      householdId: null,
      fileName: "statement.csv",
      fileSizeBytes: 2048,
      mimeType: "text/csv"
    });

    expect(preview.status).toBe("preview_placeholder");
    expect(preview.scope).toEqual({ targetScope: "personal", householdId: null });
  });

  it("falls back to the report preview placeholder for a dev network endpoint failure", async () => {
    const fetcher = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const preview = await client.previewImportReport({
      reportType: "bank_statement",
      sourceType: "file_metadata_only",
      targetScope: "shared",
      householdId: "household-1",
      fileName: "statement.csv",
      fileSizeBytes: 2048,
      mimeType: "text/csv"
    });

    expect(preview.status).toBe("preview_placeholder");
    expect(preview.scope).toEqual({ targetScope: "shared", householdId: "household-1" });
  });

  it("does not hide report preview auth, validation, or server errors behind a placeholder", async () => {
    for (const status of [400, 401, 403, 422, 500]) {
      const fetcher = vi.fn(async () => jsonResponse({ error: { code: "VISIBLE_ERROR" } }, status));
      const client = new LiveFinanceApiClient({
        baseUrl: "http://api.test",
        fetcher: fetcher as unknown as typeof fetch
      });

      await expect(
        client.previewImportReport({
          reportType: "bank_statement",
          sourceType: "file_metadata_only",
          targetScope: "personal",
          householdId: null,
          fileName: "statement.csv",
          fileSizeBytes: 2048,
          mimeType: "text/csv"
        })
      ).rejects.toThrow(`failed: ${status}`);
    }
  });

  it("adds the CSRF header to unsafe cookie-authenticated requests", async () => {
    document.cookie = "finance_csrf=csrf-from-cookie; path=/";
    const fetcher = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
      return jsonResponse({ ok: true, headers: Object.fromEntries(new Headers(init?.headers)) });
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    await (
      client as unknown as {
        request<T>(path: string, init: RequestInit): Promise<T>;
      }
    ).request("/api/v1/sessions/current", { method: "DELETE" });

    expect(fetcher).toHaveBeenCalledWith(
      "http://api.test/api/v1/sessions/current",
      expect.objectContaining({
        credentials: "include",
        method: "DELETE",
        headers: expect.any(Headers)
      })
    );
    const headers = new Headers(fetcher.mock.calls[0][1]?.headers);
    expect(headers.get("X-CSRF-Token")).toBe("csrf-from-cookie");
    expect(headers.get("Authorization")).toBeNull();
  });

  it("logs out the current PWA cookie session and clears readable csrf state", async () => {
    document.cookie = "finance_csrf=csrf-logout; path=/";
    const fetcher = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      expect(init?.method).toBe("DELETE");
      expect(headers.get("X-CSRF-Token")).toBe("csrf-logout");
      return jsonResponse(null, 204);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    await client.logout();

    expect(fetcher).toHaveBeenCalledWith(
      "http://api.test/api/v1/sessions/current",
      expect.objectContaining({
        credentials: "include",
        method: "DELETE"
      })
    );
    expect(document.cookie).not.toContain("finance_csrf=");
  });
});

function actor() {
  return {
    userId: "user-1",
    sessionId: "session-1",
    memberships: [{ householdId: "household-1", status: "active" }]
  };
}

function categoryDto(input: {
  id: string;
  name: string;
  type: "income" | "expense";
  scope: "personal" | "household";
  householdId: string | null;
  iconKey: string | null;
  color: string | null;
  version: number;
}) {
  return {
    id: input.id,
    name: input.name,
    type: input.type,
    scope: input.scope,
    ownerUserId: input.scope === "personal" ? "user-1" : null,
    householdId: input.householdId,
    iconKey: input.iconKey,
    color: input.color,
    status: "active",
    version: input.version
  };
}
