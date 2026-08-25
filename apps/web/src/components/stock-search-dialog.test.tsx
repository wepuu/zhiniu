import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StockSearchDialog } from "./stock-search-dialog";

const { searchStocks } = vi.hoisted(() => ({ searchStocks: vi.fn() }));

vi.mock("@zhaoniu/api-client", () => ({
  createZhaoniuClient: () => ({ searchStocks }),
}));

const stocks = [
  {
    symbol: "600519",
    canonical_symbol: "600519.SH",
    name: "贵州茅台",
    exchange: "SSE",
    industry: "白酒",
  },
  {
    symbol: "600518",
    canonical_symbol: "600518.SH",
    name: "康美药业",
    exchange: "SSE",
    industry: "医药",
  },
];

function renderDialog(onSelect = vi.fn(), onOpenChange = vi.fn()) {
  return {
    onSelect,
    onOpenChange,
    ...render(
      <QueryClientProvider client={new QueryClient()}>
        <StockSearchDialog
          open
          onOpenChange={onOpenChange}
          onSelect={onSelect}
        />
      </QueryClientProvider>,
    ),
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("StockSearchDialog", () => {
  it("searches by code and selects the active result with the keyboard", async () => {
    searchStocks.mockResolvedValue({ items: stocks, total: stocks.length });
    const { onSelect, onOpenChange } = renderDialog();

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "600519" },
    });
    await waitFor(() =>
      expect(searchStocks).toHaveBeenCalledWith("600519", 10),
    );
    await screen.findByText("贵州茅台");
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Enter" });

    expect(onSelect).toHaveBeenCalledWith(stocks[0]);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("supports Chinese names and shows an honest empty state", async () => {
    searchStocks.mockResolvedValueOnce({ items: [], total: 0 });
    renderDialog();

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "茅台" },
    });
    expect(
      await screen.findByText("没有找到匹配的 A 股公司。"),
    ).toBeInTheDocument();
    expect(searchStocks).toHaveBeenCalledWith("茅台", 10);
  });

  it("does not query for a single character", async () => {
    renderDialog();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "茅" } });

    await new Promise((resolve) => window.setTimeout(resolve, 250));
    expect(searchStocks).not.toHaveBeenCalled();
    expect(screen.getByText("输入至少 2 个字符开始搜索。")).toBeInTheDocument();
  });
});
