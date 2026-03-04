"use client";

import { useState } from "react";
import { useScreener } from "@/hooks/useScreener";
import ScreenerFilters from "@/components/screener/ScreenerFilters";
import ScreenerTable from "@/components/screener/ScreenerTable";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import { Download } from "lucide-react";

export default function ScreenerPage() {
  const [filters, setFilters] = useState({
    exchange_group: "",
    min_score: 0,
    regime: "",
    sort_by: "score",
    sort_dir: "desc" as "asc" | "desc",
    page: 1,
    page_size: 50,
  });

  const { data, isLoading, error } = useScreener({
    exchange_group: filters.exchange_group || undefined,
    min_score: filters.min_score || undefined,
    regime: filters.regime || undefined,
    sort_by: filters.sort_by,
    sort_dir: filters.sort_dir,
    page: filters.page,
    page_size: filters.page_size,
  });

  const handleExport = () => {
    const params = new URLSearchParams();
    if (filters.exchange_group)
      params.set("exchange_group", filters.exchange_group);
    if (filters.min_score) params.set("min_score", String(filters.min_score));
    if (filters.regime) params.set("regime", filters.regime);
    params.set("sort_by", filters.sort_by);
    params.set("sort_dir", filters.sort_dir);
    window.open(`/api/screener/export?${params.toString()}`, "_blank");
  };

  const handleSort = (column: string) => {
    setFilters((prev) => ({
      ...prev,
      sort_by: column,
      sort_dir:
        prev.sort_by === column && prev.sort_dir === "desc" ? "asc" : "desc",
      page: 1,
    }));
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Screener</h1>
          <p className="text-sm text-gray-400">
            Ranked bullish candidates across North American markets
          </p>
        </div>
        <button
          onClick={handleExport}
          className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm text-gray-300 hover:bg-gray-700"
        >
          <Download className="h-4 w-4" />
          Export CSV
        </button>
      </div>

      <ScreenerFilters filters={filters} onChange={setFilters} />

      {isLoading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-400">
          Failed to load screener data. Make sure the backend is running and data
          has been refreshed.
        </div>
      ) : data && data.items.length > 0 ? (
        <>
          <ScreenerTable
            items={data.items}
            sortBy={filters.sort_by}
            sortDir={filters.sort_dir}
            onSort={handleSort}
          />
          <div className="mt-4 flex items-center justify-between text-sm text-gray-400">
            <span>
              Showing {(filters.page - 1) * filters.page_size + 1}–
              {Math.min(filters.page * filters.page_size, data.total)} of{" "}
              {data.total}
            </span>
            <div className="flex gap-2">
              <button
                disabled={filters.page <= 1}
                onClick={() =>
                  setFilters((p) => ({ ...p, page: p.page - 1 }))
                }
                className="rounded bg-gray-800 px-3 py-1 disabled:opacity-50"
              >
                Prev
              </button>
              <button
                disabled={filters.page * filters.page_size >= data.total}
                onClick={() =>
                  setFilters((p) => ({ ...p, page: p.page + 1 }))
                }
                className="rounded bg-gray-800 px-3 py-1 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </>
      ) : (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-8 text-center text-gray-400">
          <p className="mb-2 text-lg">No data available</p>
          <p className="text-sm">
            Run the daily refresh job from Settings to populate the screener.
          </p>
        </div>
      )}

      <p className="mt-6 text-xs text-gray-600">
        Disclaimer: This tool provides probabilistic scoring for educational and
        research purposes only. It does not constitute financial advice. Past
        performance does not guarantee future results.
      </p>
    </div>
  );
}
