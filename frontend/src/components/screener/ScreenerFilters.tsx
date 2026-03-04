"use client";

interface Filters {
  exchange_group: string;
  min_score: number;
  regime: string;
  sort_by: string;
  sort_dir: "asc" | "desc";
  page: number;
  page_size: number;
}

interface ScreenerFiltersProps {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export default function ScreenerFilters({
  filters,
  onChange,
}: ScreenerFiltersProps) {
  const update = (partial: Partial<Filters>) =>
    onChange({ ...filters, ...partial, page: 1 });

  return (
    <div className="mb-4 flex flex-wrap items-center gap-4 rounded-lg border border-gray-800 bg-gray-900 p-4">
      <div>
        <label className="mb-1 block text-xs text-gray-400">Exchange</label>
        <select
          value={filters.exchange_group}
          onChange={(e) => update({ exchange_group: e.target.value })}
          className="rounded bg-gray-800 px-3 py-1.5 text-sm text-white"
        >
          <option value="">All</option>
          <option value="US">US</option>
          <option value="CA">Canada</option>
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs text-gray-400">Min Score</label>
        <input
          type="number"
          min={0}
          max={100}
          value={filters.min_score || ""}
          onChange={(e) =>
            update({ min_score: e.target.value ? Number(e.target.value) : 0 })
          }
          placeholder="0"
          className="w-20 rounded bg-gray-800 px-3 py-1.5 text-sm text-white"
        />
      </div>

      <div>
        <label className="mb-1 block text-xs text-gray-400">Regime</label>
        <select
          value={filters.regime}
          onChange={(e) => update({ regime: e.target.value })}
          className="rounded bg-gray-800 px-3 py-1.5 text-sm text-white"
        >
          <option value="">All</option>
          <option value="trending">Trending</option>
          <option value="strong_trend">Strong Trend</option>
          <option value="ranging">Ranging</option>
        </select>
      </div>
    </div>
  );
}
