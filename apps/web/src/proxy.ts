import { type NextRequest, NextResponse } from "next/server";

const sessionCookieName = process.env.AUTH_COOKIE_NAME ?? "zhaoniu_session";

export function proxy(request: NextRequest) {
  if (request.cookies.has(sessionCookieName)) return NextResponse.next();

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set(
    "next",
    `${request.nextUrl.pathname}${request.nextUrl.search}`,
  );
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/",
    "/admin/:path*",
    "/alerts/:path*",
    "/comparisons/:path*",
    "/research/:path*",
    "/saved-screens/:path*",
    "/screens/:path*",
    "/settings/:path*",
    "/stock/:path*",
    "/watchlist/:path*",
  ],
};
