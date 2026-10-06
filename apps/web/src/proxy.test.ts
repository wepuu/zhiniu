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

  it("keeps public research entry points outside the auth matcher", () => {
    const matchers = config.matcher as string[];

    expect(matchers).not.toContain("/");
    expect(matchers).not.toContain("/stock/:path*");
  });
});
