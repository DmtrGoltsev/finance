import { beforeEach, describe, expect, it, vi } from "vitest";
import { LiveFinanceApiClient } from "./client";

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
    document.cookie = "finance_csrf=; Max-Age=0; path=/";
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
            email: "demo.owner@example.test",
            password: "demo-password-only",
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
        return jsonResponse({ error: { code: "AUTHENTICATION_REQUIRED" } }, 401);
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

    const snapshot = await client.getDashboardSnapshot();

    expect(localStorageGet).not.toHaveBeenCalled();
    expect(localStorageSet).not.toHaveBeenCalled();
    expect(localStorageRemove).not.toHaveBeenCalled();
    expect(snapshot.session.accessLabel).toBe("Live API: session-");
    expect(snapshot.accounts[0]).toMatchObject({
      name: "Dev Personal Cash",
      ownerName: "Личный",
      balance: { value: 925.5, currency: "USD" }
    });
    expect(snapshot.operations[0]).toMatchObject({
      title: "Dev sample income",
      amount: { value: 250, currency: "USD" }
    });
    expect(snapshot.reports).toHaveLength(2);
  });

  it("reuses an existing cookie session before falling back to login", async () => {
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
      title: "Общий семейный отчет",
      income: { value: 250, currency: "USD" },
      expense: { value: 105.75, currency: "USD" },
      balanceDelta: { value: 144.25, currency: "USD" }
    });
    expect(snapshot.reports[1]).toMatchObject({
      mode: "combined_viewer_overview",
      title: "Сводный обзор участника"
    });
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
});

function actor() {
  return {
    userId: "user-1",
    sessionId: "session-1",
    memberships: [{ householdId: "household-1", status: "active" }]
  };
}
