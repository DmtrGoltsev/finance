import { beforeEach, describe, expect, it, vi } from "vitest";
import { LiveFinanceApiClient, getApiBaseUrl } from "./client";

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === undefined ? "" : JSON.stringify(body)),
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
    expect(
      fetcher.mock.calls.some(([url]) =>
        /\/api\/v1\/imports\//.test(String(url))
      )
    ).toBe(false);
    expect(JSON.stringify(snapshot)).not.toMatch(/\bDev\b/);
  });

  it("registers a PWA user with cookie transport and stores returned csrf state", async () => {
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      const headers = new Headers(init?.headers);

      expect(path).toBe("/api/v1/users");
      expect(init?.method).toBe("POST");
      expect(init?.credentials).toBe("include");
      expect(headers.get("X-CSRF-Token")).toBeNull();
      expect(headers.get("Authorization")).toBeNull();
      expect(init?.body).toBe(
        JSON.stringify({
          email: "new.owner@example.test",
          password: "dummy-password-12",
          transport: "pwa_cookie",
          displayName: "New Owner",
          deviceName: "iPhone Safari"
        })
      );

      return jsonResponse(
        {
          transport: "pwa_cookie",
          csrfToken: "csrf-registration",
          expiresAt: "2026-06-12T10:00:00Z",
          actor: actor()
        },
        201
      );
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const result = await client.registerUser({
      email: " new.owner@example.test ",
      password: "dummy-password-12",
      displayName: " New Owner ",
      deviceName: "iPhone Safari"
    });

    expect(result).toEqual({ status: "authenticated" });
  });

  it("treats duplicate-style registration acceptance as neutral without session state", async () => {
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");

      expect(path).toBe("/api/v1/users");
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(
        JSON.stringify({
          email: "known@example.test",
          password: "dummy-password-12",
          transport: "pwa_cookie"
        })
      );

      return jsonResponse(undefined, 202);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const result = await client.registerUser({
      email: "known@example.test",
      password: "dummy-password-12"
    });

    expect(result).toEqual({ status: "accepted" });
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
          isPaymentAccount: true,
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
      isPaymentAccount: true,
      ownershipType: "shared",
      householdId: "household-1"
    });

    expect(account.householdId).toBe("household-1");
  });

  it("creates manual income and expense with transactionDate instead of local-noon occurredAt", async () => {
    document.cookie = "finance_csrf=csrf-transaction; path=/";
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      const headers = new Headers(init?.headers);

      expect(path).toBe("/api/v1/transactions");
      expect(init?.method).toBe("POST");
      expect(headers.get("X-CSRF-Token")).toBe("csrf-transaction");
      expect(init?.body).toBe(
        JSON.stringify({
          transactionType: "expense",
          accountId: "account-1",
          categoryId: "category-1",
          amount: "42.0000",
          currency: "RUB",
          transactionDate: "2026-06-05",
          description: "Lunch",
          sourceType: "manual"
        })
      );

      return jsonResponse({
        data: {
          id: "transaction-1",
          transactionType: "expense",
          accountId: "account-1",
          counterpartyAccountId: null,
          categoryId: "category-1",
          amount: "42.0000",
          currency: "RUB",
          occurredAt: "2026-06-05T12:00:00Z",
          transactionDate: "2026-06-05",
          description: "Lunch",
          sourceType: "manual",
          version: 1
        }
      });
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const operation = await client.createDemoOperation({
      accountId: "account-1",
      categoryId: "category-1",
      currency: "RUB",
      transactionType: "expense",
      amount: 42,
      transactionDate: "2026-06-05",
      description: "Lunch"
    });

    expect(operation.date).toBe("2026-06-05");
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

  it("passes selected date boundaries to live report summary requests", async () => {
    const reportUrls: string[] = [];
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
              isPaymentAccount: true,
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
        reportUrls.push(path);
        const params = new URLSearchParams(path.split("?")[1]);
        expect(params.get("startDate")).toBe("2026-06-01");
        expect(params.get("endDate")).toBe("2026-06-30");
        return jsonResponse({
          data: {
            reportMode: params.get("reportMode"),
            currency: "USD",
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

    await client.getDashboardSnapshot({
      startDate: "2026-06-01",
      endDate: "2026-06-30"
    });

    expect(reportUrls).toHaveLength(2);
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

  it("uploads screenshot OCR as multipart form data without forcing a JSON content type", async () => {
    document.cookie = "finance_csrf=csrf-ocr; path=/";
    const image = new File(["png"], "screen.png", { type: "image/png" });
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      const headers = new Headers(init?.headers);

      expect(path).toBe("/api/v1/capture-drafts/screenshot-ocr");
      expect(init?.method).toBe("POST");
      expect(headers.get("X-CSRF-Token")).toBe("csrf-ocr");
      expect(headers.get("Content-Type")).toBeNull();
      expect(init?.body).toBeInstanceOf(FormData);
      const body = init?.body as FormData;
      expect(body.get("image")).toBe(image);
      expect(body.get("capturedAt")).toBe("2026-05-31T10:00:00.000Z");
      expect(body.get("householdId")).toBe("household-1");

      return jsonResponse({
        data: {
          captureSource: "screenshot",
          parseVersion: "category-aggregate-v1",
          recognizedAt: "2026-05-31T10:00:01.000Z",
          items: [
            {
              candidateType: "categoryAggregate",
              categoryAggregate: { externalLabel: "Products" },
              amount: "123.4500",
              currency: "RUB",
              operationCount: 3,
              description: "Products · 3 operations",
              confidence: "0.9000",
              idempotencyKey: "ocr-1",
              evidenceHash: "hash-1",
              suggestedCategoryId: "category-1"
            }
          ],
          warnings: []
        }
      });
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const result = await client.uploadScreenshotOcr(
      image,
      "2026-05-31T10:00:00.000Z",
      "household-1"
    );

    expect(result.items[0]).toMatchObject({
      externalLabel: "Products",
      amount: { value: 123.45, currency: "RUB" },
      operationCount: 3,
      suggestedCategoryId: "category-1"
    });
  });

  it("saves screenshot category mappings and creates structured capture drafts only", async () => {
    document.cookie = "finance_csrf=csrf-capture; path=/";
    const bodies: unknown[] = [];
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      const headers = new Headers(init?.headers);
      expect(headers.get("X-CSRF-Token")).toBe("csrf-capture");

      if (path === "/api/v1/capture-drafts/category-mappings" && init?.method === "PUT") {
        expect(init?.body).toBe(
          JSON.stringify({
            externalLabel: "Products",
            categoryId: "category-1",
            householdId: "household-1"
          })
        );
        return jsonResponse({ data: { categoryId: "category-1", householdId: "household-1" } });
      }

      if (path === "/api/v1/capture-drafts" && init?.method === "POST") {
        const parsed = JSON.parse(String(init?.body));
        bodies.push(parsed);
        expect(parsed).toEqual({
          idempotencyKey: "ocr-1",
          captureSource: "screenshot",
          capturedAt: "2026-05-31T10:00:00.000Z",
          amount: "123.4500",
          currency: "RUB",
          description: "Products · 3 operations",
          accountId: "account-1",
          categoryId: "category-1",
          confidence: "0.9000",
          evidenceHash: "hash-1"
        });
        expect(Object.keys(parsed)).not.toEqual(
          expect.arrayContaining(["ocrText", "rawOcrText", "body", "text", "image"])
        );
        return jsonResponse(
          {
            data: {
              id: "draft-1",
              status: "pending",
              idempotencyKey: "ocr-1",
              captureSource: "screenshot",
              capturedAt: "2026-05-31T10:00:00.000Z",
              amount: "123.4500",
              currency: "RUB",
              description: "Products · 3 operations",
              accountId: "account-1",
              categoryId: "category-1",
              confidence: "0.9000"
            }
          },
          201
        );
      }

      throw new Error(`Unexpected request: ${path}`);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    await client.saveCategoryMapping("Products", "category-1", "household-1");
    const draft = await client.createCaptureDraft({
      idempotencyKey: "ocr-1",
      captureSource: "screenshot",
      capturedAt: "2026-05-31T10:00:00.000Z",
      amount: 123.45,
      currency: "RUB",
      description: "Products · 3 operations",
      accountId: "account-1",
      categoryId: "category-1",
      confidence: 0.9,
      evidenceHash: "hash-1"
    });

    expect(bodies).toHaveLength(1);
    expect(JSON.stringify(bodies[0])).not.toMatch(/ocrText|rawOcrText|body|text|image/i);
    expect(draft).toMatchObject({
      id: "draft-1",
      occurredAt: null,
      categoryId: "category-1",
      amount: { value: 123.45, currency: "RUB" }
    });
  });

  it("lists, updates, confirms and discards pending capture drafts", async () => {
    document.cookie = "finance_csrf=csrf-drafts; path=/";
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      const headers = new Headers(init?.headers);

      if (path === "/api/v1/capture-drafts?status=pending&limit=50" && init?.method === "GET") {
        return jsonResponse({
          items: [
            {
              id: "draft-1",
              status: "pending",
              idempotencyKey: "ocr-1",
              captureSource: "screenshot",
              capturedAt: "2026-05-31T10:00:00.000Z",
              occurredDate: "2026-05-31",
              occurredAt: "2026-05-31T12:00:00.000Z",
              amount: "123.4500",
              currency: "RUB",
              description: "Products",
              accountId: null,
              categoryId: "category-1",
              confidence: "0.9000"
            }
          ],
          page: { limit: 50 }
        });
      }

      expect(headers.get("X-CSRF-Token")).toBe("csrf-drafts");
      if (path === "/api/v1/capture-drafts/draft-1" && init?.method === "PATCH") {
        const parsed = JSON.parse(String(init.body));
        expect(parsed).toEqual({
          amount: "140.0000",
          currency: "RUB",
          description: "Products reviewed",
          occurredDate: "2026-06-01",
          accountId: "account-1",
          categoryId: "category-1",
          confidence: "0.8000"
        });
        expect(Object.keys(parsed)).not.toEqual(
          expect.arrayContaining(["ocrText", "rawOcrText", "body", "text", "image"])
        );
        return jsonResponse({
          data: captureDraftDto({
            id: "draft-1",
            status: "pending",
            amount: "140.0000",
            occurredDate: "2026-06-01",
            occurredAt: "2026-06-01T12:00:00.000Z",
            description: "Products reviewed",
            accountId: "account-1"
          })
        });
      }

      if (path === "/api/v1/capture-drafts/draft-1/confirm" && init?.method === "POST") {
        return jsonResponse({
          data: captureDraftDto({
            id: "draft-1",
            status: "confirmed",
            amount: "140.0000",
            occurredDate: "2026-06-01",
            occurredAt: "2026-06-01T12:00:00.000Z",
            description: "Products reviewed",
            accountId: "account-1"
          })
        });
      }

      if (path === "/api/v1/capture-drafts/draft-2/discard" && init?.method === "POST") {
        return jsonResponse({
          data: captureDraftDto({
            id: "draft-2",
            status: "discarded",
            amount: "25.0000",
            occurredDate: null,
            occurredAt: null,
            description: "Duplicate",
            accountId: null
          })
        });
      }

      throw new Error(`Unexpected request: ${path}`);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const drafts = await client.listCaptureDrafts({ status: "pending", limit: 50 });
    const updated = await client.updateCaptureDraft({
      draftId: "draft-1",
      amount: 140,
      currency: "RUB",
      description: "Products reviewed",
      occurredDate: "2026-06-01",
      accountId: "account-1",
      categoryId: "category-1",
      confidence: 0.8
    });
    const confirmed = await client.confirmCaptureDraft("draft-1");
    const discarded = await client.discardCaptureDraft("draft-2");

    expect(drafts[0]).toMatchObject({
      id: "draft-1",
      occurredDate: "2026-05-31",
      occurredAt: "2026-05-31T12:00:00.000Z",
      amount: { value: 123.45, currency: "RUB" }
    });
    expect(updated).toMatchObject({ status: "pending", accountId: "account-1" });
    expect(confirmed.status).toBe("confirmed");
    expect(discarded.status).toBe("discarded");
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

  it("updates an operation with provided fields instead of hardcoded values", async () => {
    document.cookie = "finance_csrf=csrf-op; path=/";
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      if (path === "/api/v1/transactions/tx-1" && init?.method === "PATCH") {
        const parsed = JSON.parse(String(init.body));
        expect(parsed).toEqual({
          amount: "99.5000",
          description: "Updated lunch",
          categoryId: "cat-2",
          accountId: "acc-2",
          transactionDate: "2026-06-10",
          version: 3
        });
        return jsonResponse({
          data: {
            id: "tx-1",
            transactionType: "expense",
            accountId: "acc-2",
            counterpartyAccountId: null,
            categoryId: "cat-2",
            amount: "99.5000",
            currency: "RUB",
            occurredAt: "2026-06-10T12:00:00Z",
            transactionDate: "2026-06-10",
            description: "Updated lunch",
            sourceType: "manual",
            version: 4
          }
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });
    const result = await client.updateOperation({
      transactionId: "tx-1",
      amount: 99.5,
      description: "Updated lunch",
      categoryId: "cat-2",
      accountId: "acc-2",
      occurredDate: "2026-06-10",
      version: 3
    });
    expect(result).toMatchObject({
      id: "tx-1",
      amount: { value: -99.5, currency: "RUB" },
      date: "2026-06-10"
    });
  });

  it("deletes an operation via DELETE endpoint", async () => {
    document.cookie = "finance_csrf=csrf-del; path=/";
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      if (path === "/api/v1/transactions/tx-del" && init?.method === "DELETE") {
        return jsonResponse(null, 204);
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });
    await client.deleteOperation("tx-del");
    expect(fetcher).toHaveBeenCalledWith(
      "http://api.test/api/v1/transactions/tx-del",
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("updates a transfer with provided fields instead of hardcoded values", async () => {
    document.cookie = "finance_csrf=csrf-tf; path=/";
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      if (path === "/api/v1/transactions/tx-tf" && init?.method === "PATCH") {
        const parsed = JSON.parse(String(init.body));
        expect(parsed).toEqual({
          amount: "25.0000",
          description: "Updated transfer",
          version: 1
        });
        return jsonResponse({
          data: {
            id: "tx-tf",
            transactionType: "transfer",
            accountId: "acc-1",
            counterpartyAccountId: "acc-2",
            categoryId: null,
            amount: "25.0000",
            currency: "RUB",
            occurredAt: "2026-06-10T12:00:00Z",
            transactionDate: "2026-06-10",
            description: "Updated transfer",
            sourceType: "manual",
            version: 2
          }
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });
    const result = await client.updateTransfer({
      transactionId: "tx-tf",
      amount: 25,
      description: "Updated transfer",
      version: 1
    });
    expect(result).toMatchObject({
      id: "tx-tf",
      amount: { value: 25, currency: "RUB" }
    });
  });

  it("updates account with name, balance, currency, and assetCategoryId", async () => {
    document.cookie = "finance_csrf=csrf-acc; path=/";
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      if (path === "/api/v1/accounts/acc-1" && init?.method === "PATCH") {
        const parsed = JSON.parse(String(init.body));
        expect(parsed).toEqual({
          name: "Updated Wallet",
          currentBalance: "500.75",
          currency: "USD",
          assetCategoryId: "ac-1",
          version: 2
        });
        return jsonResponse({
          data: {
            id: "acc-1",
            name: "Updated Wallet",
            accountType: "cash",
            ownershipType: "personal",
            ownerUserId: "user-1",
            householdId: null,
            currency: "USD",
            currentBalance: "500.75",
            assetCategoryId: "ac-1",
            status: "active",
            version: 3
          }
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });
    const result = await client.updateAccount({
      accountId: "acc-1",
      name: "Updated Wallet",
      balance: 500.75,
      currency: "USD",
      assetCategoryId: "ac-1",
      version: 2
    });
    expect(result).toMatchObject({
      id: "acc-1",
      name: "Updated Wallet",
      assetCategoryId: "ac-1"
    });
  });

  it("lists, creates, updates, archives, and restores asset categories", async () => {
    document.cookie = "finance_csrf=csrf-ac; path=/";
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");

      if (path.startsWith("/api/v1/asset-categories?") && init?.method === "GET") {
        return jsonResponse({
          items: [
            {
              id: "ac-1",
              name: "Brokerage",
              scopeType: "personal",
              householdId: null,
              currency: "USD",
              assetType: "brokerage",
              manualAmount: "5000.0000",
              isInvestment: true,
              recordStatus: "active",
              version: 1
            }
          ]
        });
      }

      if (path === "/api/v1/asset-categories" && init?.method === "POST") {
        const headers = new Headers(init?.headers);
        expect(headers.get("X-CSRF-Token")).toBe("csrf-ac");
        const parsed = JSON.parse(String(init.body));
        expect(parsed.name).toBe("Gold");
        expect(parsed.scopeType).toBe("personal");
        expect(parsed.currency).toBe("XAU");
        expect(parsed.isInvestment).toBe(true);
        return jsonResponse(
          {
            data: {
              id: "ac-new",
              name: "Gold",
              scopeType: "personal",
              householdId: null,
              currency: "XAU",
              assetType: "metal",
              manualAmount: "0.0000",
              isInvestment: true,
              recordStatus: "active",
              version: 1
            }
          },
          201
        );
      }

      if (path === "/api/v1/asset-categories/ac-new" && init?.method === "PATCH") {
        const headers = new Headers(init?.headers);
        expect(headers.get("X-CSRF-Token")).toBe("csrf-ac");
        const parsed = JSON.parse(String(init.body));
        expect(parsed.manualAmount).toBe("1000.0000");
        expect(parsed.version).toBe(1);
        return jsonResponse({
          data: {
            id: "ac-new",
            name: "Gold",
            scopeType: "personal",
            householdId: null,
            currency: "XAU",
            assetType: "metal",
            manualAmount: "1000.0000",
            isInvestment: true,
            recordStatus: "active",
            version: 2
          }
        });
      }

      if (path === "/api/v1/asset-categories/ac-new/archive" && init?.method === "POST") {
        return jsonResponse({
          data: {
            id: "ac-new",
            name: "Gold",
            scopeType: "personal",
            currency: "XAU",
            assetType: "metal",
            manualAmount: "1000.0000",
            isInvestment: true,
            recordStatus: "archived",
            version: 3
          }
        });
      }

      if (path === "/api/v1/asset-categories/ac-new/restore" && init?.method === "POST") {
        return jsonResponse({
          data: {
            id: "ac-new",
            name: "Gold",
            scopeType: "personal",
            currency: "XAU",
            assetType: "metal",
            manualAmount: "1000.0000",
            isInvestment: true,
            recordStatus: "active",
            version: 4
          }
        });
      }

      throw new Error(`Unexpected request: ${path}`);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const listed = await client.listAssetCategories();
    expect(listed).toHaveLength(1);
    expect(listed[0]).toMatchObject({
      id: "ac-1",
      name: "Brokerage",
      isInvestment: true,
      manualAmount: { value: 5000, currency: "USD" }
    });

    const created = await client.createAssetCategory({
      name: "Gold",
      scopeType: "personal",
      currency: "XAU",
      isInvestment: true,
      assetType: "metal"
    });
    expect(created).toMatchObject({
      id: "ac-new",
      manualAmount: { value: 0, currency: "XAU" }
    });

    const updated = await client.updateAssetCategory({
      assetCategoryId: "ac-new",
      manualAmount: 1000,
      version: 1
    });
    expect(updated.manualAmount.value).toBe(1000);

    const archived = await client.archiveAssetCategory("ac-new");
    expect(archived.recordStatus).toBe("archived");

    const restored = await client.restoreAssetCategory("ac-new");
    expect(restored.recordStatus).toBe("active");
  });

  it("returns null when planning plan is not found for scope and month", async () => {
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      if (path.startsWith("/api/v1/planning/plans?")) {
        return jsonResponse({ error: { code: "RESOURCE_NOT_FOUND" } }, 404);
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });
    const result = await client.listPlanningPlans("personal", "2026-12");
    expect(result).toBeNull();
  });

  it("manages planning plans including CRUD, income sources, allocations, and copy", async () => {
    document.cookie = "finance_csrf=csrf-plan; path=/";
    const planDtoData = (overrides: Record<string, unknown> = {}) => ({
      id: "plan-1",
      scope: "personal",
      householdId: null,
      month: "2026-07",
      currency: "RUB",
      incomeSources: [],
      allocations: [],
      summary: {
        totalPlannedIncome: "100000.0000",
        totalConfirmedIncome: "0.0000",
        totalAllocatedAmount: "50000.0000",
        unallocatedAmount: "50000.0000",
        previousMonthSurplus: "0.0000",
        underallocated: false,
        overallocated: false
      },
      version: 1,
      ...overrides
    });
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");

      if (path.startsWith("/api/v1/planning/plans?scope=personal") && init?.method === "GET") {
        return jsonResponse({ data: planDtoData() });
      }

      if (path.startsWith("/api/v1/planning/plans/history") && init?.method === "GET") {
        return jsonResponse({
          items: [
            { id: "plan-1", scope: "personal", month: "2026-07", currency: "RUB", summary: planDtoData().summary, version: 1 }
          ]
        });
      }

      if (path === "/api/v1/planning/plans" && init?.method === "POST") {
        const headers = new Headers(init?.headers);
        expect(headers.get("X-CSRF-Token")).toBe("csrf-plan");
        const parsed = JSON.parse(String(init.body));
        expect(parsed).toEqual({
          scope: "personal",
          month: "2026-07",
          currency: "RUB"
        });
        return jsonResponse({ data: planDtoData() }, 201);
      }

      if (path === "/api/v1/planning/plans/plan-1" && init?.method === "GET") {
        return jsonResponse({ data: planDtoData() });
      }

      if (path === "/api/v1/planning/plans/plan-1/income-sources" && init?.method === "POST") {
        const headers = new Headers(init?.headers);
        expect(headers.get("X-CSRF-Token")).toBe("csrf-plan");
        const parsed = JSON.parse(String(init.body));
        expect(parsed.amount).toBe("50000.0000");
        expect(parsed.source).toBe("Salary");
        expect(parsed.dayOfMonth).toBe(5);
        return jsonResponse(
          {
            data: {
              id: "is-1",
              planId: "plan-1",
              amount: "50000.0000",
              source: "Salary",
              description: "Main salary",
              dayOfMonth: 5,
              effectiveDate: "2026-07-05",
              confirmationState: "planned",
              version: 1
            }
          },
          201
        );
      }

      if (path === "/api/v1/planning/income-sources/is-1" && init?.method === "PATCH") {
        return jsonResponse({
          data: {
            id: "is-1",
            planId: "plan-1",
            amount: "55000.0000",
            source: "Salary",
            description: "Updated salary",
            dayOfMonth: 5,
            effectiveDate: "2026-07-05",
            confirmationState: "planned",
            version: 2
          }
        });
      }

      if (path === "/api/v1/planning/income-sources/is-1/confirm" && init?.method === "POST") {
        return jsonResponse({
          data: {
            id: "is-1",
            planId: "plan-1",
            amount: "55000.0000",
            source: "Salary",
            dayOfMonth: 5,
            confirmationState: "confirmed",
            version: 3
          }
        });
      }

      if (path === "/api/v1/planning/income-sources/is-1" && init?.method === "DELETE") {
        return jsonResponse(null, 204);
      }

      if (path === "/api/v1/planning/plans/plan-1/allocations" && init?.method === "POST") {
        const headers = new Headers(init?.headers);
        expect(headers.get("X-CSRF-Token")).toBe("csrf-plan");
        const parsed = JSON.parse(String(init.body));
        expect(parsed.targetType).toBe("expense_category");
        expect(parsed.targetId).toBe("cat-1");
        expect(parsed.allocationMode).toBe("amount");
        expect(parsed.allocationValue).toBe("30000.0000");
        return jsonResponse(
          {
            data: {
              id: "alloc-1",
              planId: "plan-1",
              targetType: "expense_category",
              targetId: "cat-1",
              targetSnapshot: { name: "Food" },
              requiresAttention: false,
              allocationMode: "amount",
              allocationValue: "30000.0000",
              calculatedAmount: "30000.0000",
              recurrenceType: "regular",
              isSavingsGoal: false,
              actualAmount: "0.0000",
              varianceAmount: "-30000.0000",
              status: "no_actuals",
              version: 1
            }
          },
          201
        );
      }

      if (path === "/api/v1/planning/allocations/alloc-1" && init?.method === "PATCH") {
        return jsonResponse({
          data: {
            id: "alloc-1",
            planId: "plan-1",
            targetType: "expense_category",
            targetId: "cat-1",
            requiresAttention: false,
            allocationMode: "amount",
            allocationValue: "35000.0000",
            calculatedAmount: "35000.0000",
            recurrenceType: "regular",
            isSavingsGoal: false,
            actualAmount: "0.0000",
            varianceAmount: "-35000.0000",
            status: "no_actuals",
            version: 2
          }
        });
      }

      if (path === "/api/v1/planning/allocations/alloc-1" && init?.method === "DELETE") {
        return jsonResponse(null, 204);
      }

      if (path === "/api/v1/planning/plans/plan-1/copy" && init?.method === "POST") {
        const headers = new Headers(init?.headers);
        expect(headers.get("X-CSRF-Token")).toBe("csrf-plan");
        const parsed = JSON.parse(String(init.body));
        expect(parsed.targetMonth).toBe("2026-08");
        return jsonResponse({ data: planDtoData({ id: "plan-2", month: "2026-08" }) }, 201);
      }

      throw new Error(`Unexpected request: ${path}`);
    });
    const client = new LiveFinanceApiClient({
      baseUrl: "http://api.test",
      fetcher: fetcher as unknown as typeof fetch
    });

    const plans = await client.listPlanningPlans("personal", "2026-07");
    expect(plans).not.toBeNull();
    expect(plans!.month).toBe("2026-07");

    const history = await client.listPlanningPlanHistory("personal");
    expect(history).toHaveLength(1);

    const created = await client.createPlanningPlan({
      scope: "personal",
      month: "2026-07",
      currency: "RUB"
    });
    expect(created.id).toBe("plan-1");

    const retrieved = await client.getPlanningPlan("plan-1");
    expect(retrieved.id).toBe("plan-1");

    const income = await client.createPlanningIncomeSource({
      planId: "plan-1",
      amount: 50000,
      source: "Salary",
      description: "Main salary",
      dayOfMonth: 5
    });
    expect(income.amount.value).toBe(50000);

    const updatedIncome = await client.updatePlanningIncomeSource({
      incomeSourceId: "is-1",
      amount: 55000,
      description: "Updated salary"
    });
    expect(updatedIncome.amount.value).toBe(55000);

    const confirmed = await client.confirmPlanningIncomeSource("is-1");
    expect(confirmed.confirmed).toBe(true);

    await client.deletePlanningIncomeSource("is-1");

    const allocation = await client.createPlanningAllocation({
      planId: "plan-1",
      targetType: "expense_category",
      targetId: "cat-1",
      allocationMode: "amount",
      allocationValue: 30000
    });
    expect(allocation.allocationValue).toBe(30000);

    const updatedAlloc = await client.updatePlanningAllocation({
      allocationId: "alloc-1",
      allocationValue: 35000
    });
    expect(updatedAlloc.allocationValue).toBe(35000);

    await client.deletePlanningAllocation("alloc-1");

    const copied = await client.copyPlanningPlan({
      planId: "plan-1",
      targetMonth: "2026-08"
    });
    expect(copied.month).toBe("2026-08");
  });

  it("retrieves account balances report with asset category groups and investments", async () => {
    document.cookie = "finance_csrf=csrf-report; path=/";
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url).replace("http://api.test", "");
      if (path.startsWith("/api/v1/reports/account-balances?") && init?.method === "GET") {
        const params = new URLSearchParams(path.split("?")[1]);
        expect(params.get("reportMode")).toBe("personal");
        expect(params.get("currency")).toBe("USD");
        return jsonResponse({
          data: {
            assetCategoryGroups: [
              {
                assetCategoryId: "ac-1",
                assetCategoryName: "Brokerage",
                assetType: "brokerage",
                scopeType: "personal",
                householdId: null,
                currency: "USD",
                manualAmount: "5000.0000",
                linkedAccountsTotal: "45000.0000",
                currentBalanceTotal: "50000.0000",
                accountCount: 2,
                isInvestment: true
              }
            ],
            investmentsByCurrency: [
              { currency: "USD", investmentsTotal: "50000.0000" }
            ],
            totalsByCurrency: [
              { currency: "USD", netWorthTotal: "150000.0000" }
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

    const report = await client.getAccountBalancesReport({
      reportMode: "personal",
      currency: "USD"
    });

    expect(report.assetCategoryGroups).toHaveLength(1);
    expect(report.assetCategoryGroups[0]).toMatchObject({
      assetCategoryId: "ac-1",
      name: "Brokerage",
      isInvestment: true,
      totalAmount: { value: 50000, currency: "USD" }
    });
    expect(report.investmentsByCurrency[0]).toMatchObject({
      currency: "USD",
      investmentsTotal: { value: 50000, currency: "USD" }
    });
    expect(report.investmentsTotal).toMatchObject({
      value: 150000,
      currency: "USD"
    });
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

function captureDraftDto(input: {
  id: string;
  status: "pending" | "confirmed" | "discarded";
  amount: string;
  occurredDate?: string | null;
  occurredAt: string | null;
  description: string;
  accountId: string | null;
}) {
  return {
    id: input.id,
    status: input.status,
    idempotencyKey: `ocr-${input.id}`,
    captureSource: "screenshot",
    capturedAt: "2026-05-31T10:00:00.000Z",
    occurredDate: input.occurredDate ?? null,
    occurredAt: input.occurredAt,
    amount: input.amount,
    currency: "RUB",
    description: input.description,
    accountId: input.accountId,
    categoryId: "category-1",
    confidence: "0.8000"
  };
}
