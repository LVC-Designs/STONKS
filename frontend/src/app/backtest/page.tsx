"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useBacktestRuns, useDeleteBacktest, useSweep } from "@/hooks/useBacktest";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import { Plus, GitCompare, Trash2, FlaskConical, Zap, AlertTriangle, Info } from "lucide-react";
import type { BacktestRun } from "@/lib/types";

const statusColors: Record<string, string> = {
  pending: "bg-yellow-500/20 text-yellow-400",
  running: "bg-blue-500/20 text-blue-400",
  completed: "bg-emerald-500/20 text-emerald-400",
  failed: "bg-red-500/20 text-red-400",
};

function formatDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString();
}

function formatNum(n: number | null | undefined, decimals = 2) {
  if (n == null) return "—";
  return n.toFixed(decimals);
}

function parseCommaSeparated(s: string): number[] {
  return s.split(",").map((v) => parseFloat(v.trim())).filter((v) => !isNaN(v));
}

export default function BacktestDashboard() {
  const router = useRouter();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [showSweep, setShowSweep] = useState(false);
  const [sweepFrom, setSweepFrom] = useState("2024-06-01");
  const [sweepTo, setSweepTo] = useState("2025-12-31");
  const [minScoresStr, setMinScoresStr] = useState("30, 40, 50, 60");
  const [targetPctsStr, setTargetPctsStr] = useState("3, 5, 8");
  const [targetDaysStr, setTargetDaysStr] = useState("10, 20, 30");
  const [maxDdStr, setMaxDdStr] = useState("-2, -3, -5");

  const { data, isLoading, error } = useBacktestRuns({
    status: statusFilter || undefined,
    page,
    page_size: 20,
  });

  const deleteMutation = useDeleteBacktest();
  const sweepMutation = useSweep();

  const minScores = parseCommaSeparated(minScoresStr);
  const targetPcts = parseCommaSeparated(targetPctsStr);
  const targetDaysList = parseCommaSeparated(targetDaysStr).map(Math.round);
  const maxDdPcts = parseCommaSeparated(maxDdStr);
  const totalCombos = minScores.length * targetPcts.length * targetDaysList.length * maxDdPcts.length;

  const handleSweep = async () => {
    if (totalCombos === 0) return;
    await sweepMutation.mutateAsync({
      date_from: sweepFrom,
      date_to: sweepTo,
      exchange_groups: ["US"],
      min_scores: minScores,
      target_pcts: targetPcts,
      target_days_list: targetDaysList,
      max_drawdown_pcts: maxDdPcts,
      portfolio: {
        starting_capital: 10000,
        max_positions: 5,
        position_size_pct: 20,
        use_equal_weight: true,
      },
    });
    setShowSweep(false);
  };

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleCompare = () => {
    if (selected.size < 2) return;
    const ids = Array.from(selected).join(",");
    router.push(`/backtest/compare?ids=${ids}`);
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this backtest run and all its data?")) return;
    deleteMutation.mutate(id);
    setSelected((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  const allIds = data?.items.map((r: BacktestRun) => r.id) ?? [];
  const allSelected = allIds.length > 0 && allIds.every((id: number) => selected.has(id));

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(allIds));
    }
  };

  const handleDeleteSelected = async () => {
    if (selected.size === 0) return;
    if (!confirm(`Delete ${selected.size} backtest run(s) and all their data?`)) return;
    for (const id of selected) {
      deleteMutation.mutate(id);
    }
    setSelected(new Set());
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Backtests</h1>
          <p className="text-sm text-gray-400">
            Run and compare strategy backtests
          </p>
        </div>
        <div className="flex gap-2">
          {selected.size > 0 && (
            <button
              onClick={handleDeleteSelected}
              className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-500"
            >
              <Trash2 className="h-4 w-4" />
              Delete ({selected.size})
            </button>
          )}
          {selected.size >= 2 && (
            <button
              onClick={handleCompare}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500"
            >
              <GitCompare className="h-4 w-4" />
              Compare ({selected.size})
            </button>
          )}
          <button
            onClick={() => setShowSweep(!showSweep)}
            className="flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm text-white hover:bg-amber-500"
          >
            <Zap className="h-4 w-4" />
            Start Analyzing Market
          </button>
          <Link
            href="/backtest/new"
            className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-500"
          >
            <Plus className="h-4 w-4" />
            New Backtest
          </Link>
        </div>
      </div>

      {/* Sweep Panel */}
      {showSweep && (
        <div className="mb-6 rounded-lg border border-amber-500/30 bg-amber-500/5 p-6">
          <h2 className="mb-1 text-lg font-semibold text-white">
            Automated Strategy Sweep
          </h2>
          <p className="mb-4 text-sm text-gray-400">
            Tests every combination of the parameters below. Edit values (comma-separated) to customize the grid.
          </p>
          <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Date From
              </label>
              <input
                type="date"
                value={sweepFrom}
                onChange={(e) => setSweepFrom(e.target.value)}
                className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Date To
              </label>
              <input
                type="date"
                value={sweepTo}
                onChange={(e) => setSweepTo(e.target.value)}
                className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
              />
            </div>
          </div>
          <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Min Scores
              </label>
              <input
                type="text"
                value={minScoresStr}
                onChange={(e) => setMinScoresStr(e.target.value)}
                className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                placeholder="30, 40, 50, 60"
              />
              <span className="mt-0.5 block text-xs text-gray-500">
                {minScores.length} values
              </span>
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Target % (profit)
              </label>
              <input
                type="text"
                value={targetPctsStr}
                onChange={(e) => setTargetPctsStr(e.target.value)}
                className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                placeholder="3, 5, 8"
              />
              <span className="mt-0.5 block text-xs text-gray-500">
                {targetPcts.length} values
              </span>
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Holding Days
              </label>
              <input
                type="text"
                value={targetDaysStr}
                onChange={(e) => setTargetDaysStr(e.target.value)}
                className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                placeholder="10, 20, 30"
              />
              <span className="mt-0.5 block text-xs text-gray-500">
                {targetDaysList.length} values
              </span>
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Max Drawdown %
              </label>
              <input
                type="text"
                value={maxDdStr}
                onChange={(e) => setMaxDdStr(e.target.value)}
                className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                placeholder="-2, -3, -5"
              />
              <span className="mt-0.5 block text-xs text-gray-500">
                {maxDdPcts.length} values
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleSweep}
              disabled={sweepMutation.isPending || totalCombos === 0}
              className="flex items-center gap-2 rounded-lg bg-amber-600 px-5 py-2 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50"
            >
              <Zap className="h-4 w-4" />
              {sweepMutation.isPending
                ? "Launching..."
                : `Launch ${totalCombos} Backtests`}
            </button>
            {sweepMutation.isSuccess && (
              <span className="flex items-center text-sm text-emerald-400">
                Launched {sweepMutation.data.total_combinations} backtests
              </span>
            )}
            <span className="text-xs text-gray-500">
              {minScores.length} scores x {targetPcts.length} targets x {targetDaysList.length} days x {maxDdPcts.length} drawdowns
            </span>
            <button
              onClick={() => setShowSweep(false)}
              className="ml-auto rounded-lg bg-gray-800 px-4 py-2 text-sm text-gray-400 hover:text-white"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 flex gap-3">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-300"
        >
          <option value="">All statuses</option>
          <option value="completed">Completed</option>
          <option value="running">Running</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-400">
          Failed to load backtests.
        </div>
      ) : data && data.items.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-lg border border-gray-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-900 text-left text-gray-400">
                  <th className="px-3 py-3 w-10">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleSelectAll}
                      className="rounded border-gray-600"
                    />
                  </th>
                  <th className="px-3 py-3">Name</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Date Range</th>
                  <th className="px-3 py-3 text-right">Trades</th>
                  <th className="px-3 py-3 text-right">Win Rate</th>
                  <th className="px-3 py-3 text-right">Sharpe</th>
                  <th className="px-3 py-3 text-right">Return</th>
                  <th className="px-3 py-3 text-right">P-Value</th>
                  <th className="px-3 py-3">Created</th>
                  <th className="px-3 py-3 w-10"></th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((run: BacktestRun) => {
                  const r = run.results;
                  const d = run.diagnostics;
                  const hasWarning = d && d.reasons && d.reasons.length > 0;
                  return (
                    <tr
                      key={run.id}
                      className="border-b border-gray-800/50 hover:bg-gray-800/50 cursor-pointer"
                      onClick={() => router.push(`/backtest/${run.id}`)}
                    >
                      <td
                        className="px-3 py-3"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSelect(run.id);
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={selected.has(run.id)}
                          readOnly
                          className="rounded border-gray-600"
                        />
                      </td>
                      <td className="px-3 py-3 text-white font-medium">
                        <div className="flex items-center gap-2">
                          {run.name || `Run #${run.id}`}
                          {hasWarning && (
                            <span title={d.reasons.join(" | ")}>
                              <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                            </span>
                          )}
                        </div>
                        {r?.total_trades === 0 && d?.max_signal_score_in_range != null && (
                          <div className="mt-0.5 text-xs text-amber-400/70">
                            Max score: {d.max_signal_score_in_range}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusColors[run.status] || "bg-gray-700 text-gray-400"}`}
                        >
                          {run.status}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-gray-400">
                        {run.date_from} &rarr; {run.date_to}
                      </td>
                      <td className="px-3 py-3 text-right text-gray-300">
                        {r?.total_trades ?? run.signal_count ?? "—"}
                      </td>
                      <td className="px-3 py-3 text-right text-gray-300">
                        {r?.win_rate != null ? `${(r.win_rate * 100).toFixed(1)}%` : "—"}
                      </td>
                      <td className="px-3 py-3 text-right text-gray-300">
                        {r?.portfolio?.sharpe_ratio != null
                          ? formatNum(r.portfolio.sharpe_ratio)
                          : "—"}
                      </td>
                      <td
                        className={`px-3 py-3 text-right font-medium ${
                          r?.portfolio?.total_return != null
                            ? r.portfolio.total_return >= 0
                              ? "text-emerald-400"
                              : "text-red-400"
                            : "text-gray-400"
                        }`}
                      >
                        {r?.portfolio?.total_return != null
                          ? `${formatNum(r.portfolio.total_return)}%`
                          : "—"}
                      </td>
                      <td className="px-3 py-3 text-right text-gray-300">
                        {r?.p_value != null ? formatNum(r.p_value, 4) : "—"}
                      </td>
                      <td className="px-3 py-3 text-gray-500 text-xs">
                        {formatDate(run.created_at)}
                      </td>
                      <td
                        className="px-3 py-3"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(run.id);
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-gray-600 hover:text-red-400" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="mt-4 flex items-center justify-between text-sm text-gray-400">
            <span>
              Showing {(page - 1) * 20 + 1}–{Math.min(page * 20, data.total)} of{" "}
              {data.total}
            </span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded bg-gray-800 px-3 py-1 disabled:opacity-50"
              >
                Prev
              </button>
              <button
                disabled={page * 20 >= data.total}
                onClick={() => setPage((p) => p + 1)}
                className="rounded bg-gray-800 px-3 py-1 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </>
      ) : (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-8 text-center text-gray-400">
          <FlaskConical className="mx-auto mb-3 h-10 w-10 text-gray-600" />
          <p className="mb-2 text-lg">No backtests yet</p>
          <p className="mb-4 text-sm">
            Create your first backtest to start testing strategies.
          </p>
          <Link
            href="/backtest/new"
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-500"
          >
            <Plus className="h-4 w-4" />
            New Backtest
          </Link>
        </div>
      )}
    </div>
  );
}
