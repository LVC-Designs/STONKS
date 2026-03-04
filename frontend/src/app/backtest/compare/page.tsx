"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useBacktestCompare } from "@/hooks/useBacktest";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import { ArrowLeft } from "lucide-react";

function fmt(n: number | null | undefined, d = 2) {
  if (n == null) return "—";
  return n.toFixed(d);
}

function pctFmt(n: number | null | undefined) {
  if (n == null) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

interface MetricRow {
  label: string;
  getValue: (r: Record<string, unknown> | null) => number | null | undefined;
  format: (v: number | null | undefined) => string;
  higherIsBetter: boolean;
}

const metrics: MetricRow[] = [
  {
    label: "Total Trades",
    getValue: (r) => r?.total_trades as number,
    format: (v) => (v != null ? String(v) : "—"),
    higherIsBetter: true,
  },
  {
    label: "Win Rate",
    getValue: (r) => r?.win_rate as number,
    format: pctFmt,
    higherIsBetter: true,
  },
  {
    label: "Avg Return",
    getValue: (r) => r?.avg_return as number,
    format: (v) => `${fmt(v)}%`,
    higherIsBetter: true,
  },
  {
    label: "Profit Factor",
    getValue: (r) => r?.profit_factor as number,
    format: (v) => fmt(v),
    higherIsBetter: true,
  },
  {
    label: "Expectancy",
    getValue: (r) => r?.expectancy as number,
    format: (v) => fmt(v),
    higherIsBetter: true,
  },
  {
    label: "Sharpe Ratio",
    getValue: (r) => (r?.portfolio as Record<string, number>)?.sharpe_ratio,
    format: (v) => fmt(v),
    higherIsBetter: true,
  },
  {
    label: "Total Return",
    getValue: (r) => (r?.portfolio as Record<string, number>)?.total_return,
    format: (v) => `${fmt(v)}%`,
    higherIsBetter: true,
  },
  {
    label: "CAGR",
    getValue: (r) => (r?.portfolio as Record<string, number>)?.cagr,
    format: (v) => `${fmt(v)}%`,
    higherIsBetter: true,
  },
  {
    label: "Max Drawdown",
    getValue: (r) => (r?.portfolio as Record<string, number>)?.max_drawdown,
    format: (v) => `${fmt(v)}%`,
    higherIsBetter: false,
  },
  {
    label: "P-Value",
    getValue: (r) => r?.p_value as number,
    format: (v) => fmt(v, 4),
    higherIsBetter: false,
  },
  {
    label: "Avg Win",
    getValue: (r) => r?.avg_win as number,
    format: (v) => `${fmt(v)}%`,
    higherIsBetter: true,
  },
  {
    label: "Avg Loss",
    getValue: (r) => r?.avg_loss as number,
    format: (v) => `${fmt(v)}%`,
    higherIsBetter: false,
  },
  {
    label: "Avg Days Held",
    getValue: (r) => r?.avg_days_held as number,
    format: (v) => fmt(v, 1),
    higherIsBetter: false,
  },
];

export default function ComparePage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <CompareContent />
    </Suspense>
  );
}

function CompareContent() {
  const params = useSearchParams();
  const idsParam = params.get("ids") || "";
  const ids = idsParam
    .split(",")
    .filter(Boolean)
    .map(Number)
    .filter((n) => !isNaN(n));

  const { data, isLoading, error } = useBacktestCompare(ids);

  if (isLoading) return <LoadingSpinner />;
  if (error || !data)
    return <div className="text-red-400">Failed to load comparison.</div>;

  const runs = data.runs;

  // For each metric row, find the best value
  const getBest = (row: MetricRow): number | null => {
    const values = runs
      .map((r) => row.getValue(r.results as unknown as Record<string, unknown>))
      .filter((v): v is number => v != null);
    if (values.length === 0) return null;
    return row.higherIsBetter ? Math.max(...values) : Math.min(...values);
  };

  return (
    <div>
      <Link
        href="/backtest"
        className="mb-3 inline-flex items-center gap-1 text-sm text-gray-400 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Backtests
      </Link>

      <h1 className="mb-2 text-2xl font-bold text-white">Compare Strategies</h1>
      <p className="mb-6 text-sm text-gray-400">
        Side-by-side comparison of {runs.length} backtest runs
      </p>

      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 bg-gray-900">
              <th className="px-4 py-3 text-left text-gray-400">Metric</th>
              {runs.map((run) => (
                <th key={run.id} className="px-4 py-3 text-center">
                  <Link
                    href={`/backtest/${run.id}`}
                    className="text-emerald-400 hover:underline"
                  >
                    {run.name || `Run #${run.id}`}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {/* Strategy config summary row */}
            <tr className="border-b border-gray-800/50 bg-gray-900/50">
              <td className="px-4 py-2 text-gray-500 text-xs">Min Score</td>
              {runs.map((run) => (
                <td key={run.id} className="px-4 py-2 text-center text-gray-300 text-xs">
                  {(run.config as unknown as Record<string, unknown>)?.min_score as number ?? "—"}
                </td>
              ))}
            </tr>
            <tr className="border-b border-gray-800/50 bg-gray-900/50">
              <td className="px-4 py-2 text-gray-500 text-xs">Target %</td>
              {runs.map((run) => (
                <td key={run.id} className="px-4 py-2 text-center text-gray-300 text-xs">
                  {(run.config as unknown as Record<string, unknown>)?.target_pct as number ?? "—"}%
                </td>
              ))}
            </tr>

            {/* Metric rows */}
            {metrics.map((row) => {
              const best = getBest(row);
              return (
                <tr key={row.label} className="border-b border-gray-800/50">
                  <td className="px-4 py-3 font-medium text-gray-300">
                    {row.label}
                  </td>
                  {runs.map((run) => {
                    const val = row.getValue(
                      run.results as unknown as Record<string, unknown>
                    );
                    const isBest = val != null && val === best && runs.length > 1;
                    return (
                      <td
                        key={run.id}
                        className={`px-4 py-3 text-center ${
                          isBest
                            ? "font-bold text-emerald-400"
                            : "text-gray-300"
                        }`}
                      >
                        {row.format(val)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
