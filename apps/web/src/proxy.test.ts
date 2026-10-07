import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { config, proxy } from "./proxy";

describe("authenticated application proxy", () => {
  it("keeps an unauthenticated visitor on the login flow", () => {
    const response = proxy(
      new NextRequest("https://app.zhiniu.cc/watchlist?group=primary"),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://app.zhiniu.cc/login?next=%2Fwatchlist%3Fgroup%3Dprimary",
    );
  });

  it("allows a request carrying the session cookie to continue", () => {
    const response = proxy(
      new NextRequest("https://app.zhiniu.cc/watchlist", {
        headers: { cookie: "zhaoniu_session=opaque-session" },
      }),
    );

    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it("protects the home and company-research entry points", () => {
    const matchers = config.matcher as string[];

    expect(matchers).toContain("/");
    expect(matchers).toContain("/stock/:path*");
  });

  it("redirects an unauthenticated home request to login", () => {
    const response = proxy(new NextRequest("https://app.zhiniu.cc/"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://app.zhiniu.cc/login?next=%2F",
    );
  });

  it("preserves a company page as the post-login destination", () => {
    const response = proxy(
      new NextRequest("https://app.zhiniu.cc/stock/600519.SH?tab=research"),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://app.zhiniu.cc/login?next=%2Fstock%2F600519.SH%3Ftab%3Dresearch",
    );
  });
});
