"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  useBacktestDetail,
  useBacktestSignals,
  useBacktestEquity,
} from "@/hooks/useBacktest";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import EquityChart from "@/components/backtest/EquityChart";
import { ArrowLeft, TrendingUp, TrendingDown, Target, BarChart3, Clock, Activity } from "lucide-react";

function fmt(n: number | null | undefined, d = 2) {
  if (n == null) return "—";
  return n.toFixed(d);
}

function pct(n: number | null | undefined) {
  if (n == null) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

const outcomeColors: Record<string, string> = {
  win: "text-emerald-400",
  loss: "text-red-400",
  timeout: "text-gray-400",
  no_data: "text-gray-600",
};

export default function BacktestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const runId = id ? Number(id) : null;

  const { data: detail, isLoading } = useBacktestDetail(runId);
  const { data: equityData } = useBacktestEquity(
    detail?.status === "completed" ? runId : null
  );
  const [sigPage, setSigPage] = useState(1);
  const { data: sigData } = useBacktestSignals(
    detail?.status === "completed" ? runId : null,
    sigPage,
  );

  if (isLoading) return <LoadingSpinner />;
  if (!detail) return <div className="text-gray-400">Backtest not found.</div>;

  const r = detail.results;
  const pm = r?.portfolio;
  const wf = r?.walk_forward;
  const diag = detail.diagnostics as Record<string, unknown> | null;

  return (
    <div>
      {/* Header */}
      <Link
        href="/backtest"
        className="mb-3 inline-flex items-center gap-1 text-sm text-gray-400 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Backtests
      </Link>

      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            {detail.name || `Backtest #${detail.id}`}
          </h1>
          <p className="text-sm text-gray-400">
            {detail.date_from} &rarr; {detail.date_to} | {detail.signal_count} signals
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-sm font-medium ${
            detail.status === "completed"
              ? "bg-emerald-500/20 text-emerald-400"
              : detail.status === "running"
                ? "bg-blue-500/20 text-blue-400"
                : detail.status === "failed"
                  ? "bg-red-500/20 text-red-400"
                  : "bg-yellow-500/20 text-yellow-400"
          }`}
        >
          {detail.status}
        </span>
      </div>

      {/* Running / pending status */}
      {(detail.status === "running" || detail.status === "pending") && (
        <div className="mb-6 rounded-lg border border-blue-500/30 bg-blue-500/10 p-6 text-center">
          <LoadingSpinner />
          <p className="mt-3 text-blue-300">
            {typeof r === "object" && r && "progress" in r
              ? (r as Record<string, string>).progress
              : "Backtest is running..."}
          </p>
        </div>
      )}

      {/* Failed */}
      {detail.status === "failed" && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-400">
          {typeof r === "object" && r && "error" in r
            ? (r as Record<string, string>).error
            : "Backtest failed."}
        </div>
      )}

      {/* Diagnostics Panel */}
      {diag && (
        <div className="mb-6 rounded-lg border border-gray-700 bg-gray-900 p-4">
          <h3 className="mb-2 text-sm font-semibold text-gray-300">Diagnostics</h3>
          <div className="mb-2 grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
            <div>
              <span className="text-gray-500">Tickers:</span>{" "}
              <span className="text-gray-300">{diag.tickers_in_universe as number}</span>
            </div>
            <div>
              <span className="text-gray-500">OHLCV bars:</span>{" "}
              <span className="text-gray-300">
                {(diag.bars_available as Record<string, unknown>)?.total_rows as number}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Scores computed:</span>{" "}
              <span className="text-gray-300">{diag.signals_computed as number}</span>
            </div>
            <div>
              <span className="text-gray-500">Signals above threshold:</span>{" "}
              <span className="text-gray-300">{diag.signals_meeting_threshold as number}</span>
            </div>
            {diag.max_signal_score_in_range != null && (
              <div>
                <span className="text-gray-500">Max score in range:</span>{" "}
                <span className="text-amber-400 font-medium">{diag.max_signal_score_in_range as number}</span>
              </div>
            )}
            {diag.min_signal_score_in_range != null && (
              <div>
                <span className="text-gray-500">Min score in range:</span>{" "}
                <span className="text-gray-300">{diag.min_signal_score_in_range as number}</span>
              </div>
            )}
          </div>
          {Array.isArray(diag.reasons) && (diag.reasons as string[]).length > 0 && (
            <div className="mt-2 rounded border border-amber-500/20 bg-amber-500/5 p-2">
              {(diag.reasons as string[]).map((reason, i) => (
                <p key={i} className="text-xs text-amber-400">
                  {reason}
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Metrics cards */}
      {detail.status === "completed" && r && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
            <MetricCard
              icon={<Target className="h-5 w-5" />}
              label="Win Rate"
              value={pct(r.win_rate)}
              color={r.win_rate >= 0.5 ? "emerald" : "red"}
            />
            <MetricCard
              icon={<BarChart3 className="h-5 w-5" />}
              label="Sharpe Ratio"
              value={fmt(pm?.sharpe_ratio)}
              color={(pm?.sharpe_ratio ?? 0) >= 1 ? "emerald" : "yellow"}
            />
            <MetricCard
              icon={<TrendingUp className="h-5 w-5" />}
              label="Total Return"
              value={`${fmt(pm?.total_return)}%`}
              color={(pm?.total_return ?? 0) >= 0 ? "emerald" : "red"}
            />
            <MetricCard
              icon={<TrendingDown className="h-5 w-5" />}
              label="Max Drawdown"
              value={`${fmt(pm?.max_drawdown)}%`}
              color="red"
            />
            <MetricCard
              icon={<Activity className="h-5 w-5" />}
              label="Profit Factor"
              value={r.profit_factor != null ? fmt(r.profit_factor) : "—"}
              color={(r.profit_factor ?? 0) >= 1.5 ? "emerald" : "yellow"}
            />
            <MetricCard
              icon={<Clock className="h-5 w-5" />}
              label="Total Trades"
              value={String(r.total_trades)}
              color="gray"
            />
          </div>

          {/* Secondary metrics */}
          <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatRow label="Avg Win" value={`${fmt(r.avg_win)}%`} />
            <StatRow label="Avg Loss" value={`${fmt(r.avg_loss)}%`} />
            <StatRow label="Avg Days Held" value={fmt(r.avg_days_held, 1)} />
            <StatRow label="Expectancy" value={fmt(r.expectancy)} />
            <StatRow label="CAGR" value={`${fmt(pm?.cagr)}%`} />
            <StatRow
              label="Final Equity"
              value={pm?.final_equity != null ? `$${pm.final_equity.toLocaleString()}` : "—"}
            />
            <StatRow label="P-Value" value={r.p_value != null ? fmt(r.p_value, 4) : "—"} />
            <StatRow label="Wins / Losses / Timeouts" value={`${r.wins} / ${r.losses} / ${r.timeouts}`} />
          </div>

          {/* Equity Curve Chart */}
          {equityData?.equity_curve && equityData.equity_curve.length > 0 && (
            <div className="mb-6 rounded-lg border border-gray-800 bg-gray-900 p-4">
              <h2 className="mb-3 text-lg font-semibold text-white">Equity Curve</h2>
              <EquityChart data={equityData.equity_curve} />
            </div>
          )}

          {/* Walk-Forward Breakdown */}
          {wf && (
            <div className="mb-6 rounded-lg border border-gray-800 bg-gray-900 p-4">
              <h2 className="mb-3 text-lg font-semibold text-white">
                Walk-Forward Breakdown
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-400">
                      <th className="px-3 py-2 text-left">Window</th>
                      <th className="px-3 py-2 text-right">Trades</th>
                      <th className="px-3 py-2 text-right">Win Rate</th>
                      <th className="px-3 py-2 text-right">Avg Return</th>
                      <th className="px-3 py-2 text-right">Profit Factor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(["train", "validation", "oos"] as const).map((w) => {
                      const m = wf[w];
                      if (!m) return null;
                      return (
                        <tr key={w} className="border-b border-gray-800/50">
                          <td className="px-3 py-2 font-medium text-white capitalize">
                            {w === "oos" ? "Out-of-Sample" : w}
                          </td>
                          <td className="px-3 py-2 text-right text-gray-300">
                            {m.total_trades}
                          </td>
                          <td className="px-3 py-2 text-right text-gray-300">
                            {pct(m.win_rate)}
                          </td>
                          <td className="px-3 py-2 text-right text-gray-300">
                            {fmt(m.avg_return)}%
                          </td>
                          <td className="px-3 py-2 text-right text-gray-300">
                            {m.profit_factor != null ? fmt(m.profit_factor) : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Strategy Config */}
          <details className="mb-6 rounded-lg border border-gray-800 bg-gray-900">
            <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-white">
              Strategy Configuration
            </summary>
            <pre className="overflow-x-auto border-t border-gray-800 px-4 py-3 text-xs text-gray-400">
              {JSON.stringify(detail.config, null, 2)}
            </pre>
          </details>

          {/* Signals Table */}
          {sigData && sigData.items.length > 0 && (
            <div className="rounded-lg border border-gray-800">
              <div className="border-b border-gray-800 bg-gray-900 px-4 py-3">
                <h2 className="text-lg font-semibold text-white">
                  Signals ({sigData.total})
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800 bg-gray-900/50 text-gray-400">
                      <th className="px-3 py-2 text-left">Ticker</th>
                      <th className="px-3 py-2 text-left">Date</th>
                      <th className="px-3 py-2 text-right">Score</th>
                      <th className="px-3 py-2 text-right">Entry</th>
                      <th className="px-3 py-2 text-right">Target</th>
                      <th className="px-3 py-2 text-right">Stop</th>
                      <th className="px-3 py-2 text-center">Outcome</th>
                      <th className="px-3 py-2 text-right">Return</th>
                      <th className="px-3 py-2 text-right">Days</th>
                      <th className="px-3 py-2 text-right">Max DD</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sigData.items.map((sig) => (
                      <tr key={sig.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                        <td className="px-3 py-2">
                          <Link
                            href={`/ticker/${sig.ticker_symbol}`}
                            className="font-medium text-emerald-400 hover:underline"
                          >
                            {sig.ticker_symbol}
                          </Link>
                        </td>
                        <td className="px-3 py-2 text-gray-400">{sig.signal_date}</td>
                        <td className="px-3 py-2 text-right text-gray-300">
                          {fmt(sig.score, 1)}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-300">
                          ${fmt(sig.entry_price)}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-300">
                          ${fmt(sig.target_price)}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-300">
                          ${fmt(sig.stop_price)}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span className={`font-medium ${outcomeColors[sig.outcome || ""] || "text-gray-500"}`}>
                            {sig.outcome || "—"}
                          </span>
                        </td>
                        <td
                          className={`px-3 py-2 text-right font-medium ${
                            (sig.actual_return ?? 0) >= 0
                              ? "text-emerald-400"
                              : "text-red-400"
                          }`}
                        >
                          {sig.actual_return != null ? `${fmt(sig.actual_return)}%` : "—"}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-400">
                          {sig.days_held ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-right text-red-400">
                          {sig.max_drawdown != null ? `${fmt(sig.max_drawdown)}%` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {sigData.total > 50 && (
                <div className="flex items-center justify-between border-t border-gray-800 px-4 py-3 text-sm text-gray-400">
                  <span>
                    Page {sigPage} of {Math.ceil(sigData.total / 50)}
                  </span>
                  <div className="flex gap-2">
                    <button
                      disabled={sigPage <= 1}
                      onClick={() => setSigPage((p) => p - 1)}
                      className="rounded bg-gray-800 px-3 py-1 disabled:opacity-50"
                    >
                      Prev
                    </button>
                    <button
                      disabled={sigPage * 50 >= sigData.total}
                      onClick={() => setSigPage((p) => p + 1)}
                      className="rounded bg-gray-800 px-3 py-1 disabled:opacity-50"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: "border-emerald-500/30 text-emerald-400",
    red: "border-red-500/30 text-red-400",
    yellow: "border-yellow-500/30 text-yellow-400",
    gray: "border-gray-700 text-gray-300",
  };
  return (
    <div
      className={`rounded-lg border bg-gray-900 p-4 ${colorMap[color] || colorMap.gray}`}
    >
      <div className="mb-1 flex items-center gap-2 text-xs text-gray-500">
        {icon}
        {label}
      </div>
      <div className="text-xl font-bold">{value}</div>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 px-4 py-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-sm font-medium text-gray-200">{value}</div>
    </div>
  );
}
