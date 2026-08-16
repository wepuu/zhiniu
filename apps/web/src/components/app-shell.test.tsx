import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AppShell } from "./app-shell";

afterEach(cleanup);

describe("AppShell", () => {
  it("renders the application smoke content", () => {
    render(
      <AppShell>
        <h1>研究工作区</h1>
      </AppShell>,
    );
    expect(
      screen.getByRole("heading", { name: "研究工作区" }),
    ).toBeInTheDocument();
  });

  it("keeps independent desktop and mobile navigation compositions", () => {
    render(
      <AppShell>
        <span>content</span>
      </AppShell>,
    );
    expect(screen.getByTestId("desktop-sidebar")).toHaveClass(
      "hidden",
      "md:block",
    );
    expect(screen.getByTestId("mobile-navigation")).toHaveClass("md:hidden");
    expect(
      screen.getByRole("navigation", { name: "移动端主导航" }),
    ).toBeInTheDocument();
  });
});
