import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isStockSearchQueryReady,
  StockSearchDialog,
} from "./stock-search-dialog";

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

  it("queries a single Chinese character", async () => {
    searchStocks.mockResolvedValue({ items: stocks, total: stocks.length });
    renderDialog();

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "茅" } });
    await waitFor(() => expect(searchStocks).toHaveBeenCalledWith("茅", 10));
  });

  it("accepts full pinyin and initials but rejects one Latin character", () => {
    expect(isStockSearchQueryReady("guizhoumaotai")).toBe(true);
    expect(isStockSearchQueryReady("gzmt")).toBe(true);
    expect(isStockSearchQueryReady("g")).toBe(false);
  });
});
