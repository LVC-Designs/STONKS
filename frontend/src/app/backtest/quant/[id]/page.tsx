"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuantBacktestDetail } from "@/hooks/useQuantBacktest";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import EquityChart from "@/components/backtest/EquityChart";
import {
  ArrowLeft,
  Shield,
  TrendingUp,
  TrendingDown,
  Target,
  BarChart3,
  AlertTriangle,
  Trophy,
  Activity,
} from "lucide-react";
import type { QuantMetrics, QuantCandidate } from "@/lib/types";

function fmt(n: number | null | undefined, d = 2) {
  if (n == null) return "\u2014";
  return n.toFixed(d);
}

function pct(n: number | null | undefined) {
  if (n == null) return "\u2014";
  return `${(n * 100).toFixed(1)}%`;
}

function stabilityColor(s: number | null | undefined) {
  if (s == null) return "text-gray-500";
  if (s >= 70) return "text-emerald-400";
  if (s >= 40) return "text-yellow-400";
  return "text-red-400";
}

export default function QuantBacktestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qbId = id ? Number(id) : null;
  const { data: detail, isLoading } = useQuantBacktestDetail(qbId);

  if (isLoading) return <LoadingSpinner />;
  if (!detail) return <div className="text-gray-400">Not found.</div>;

  const r = detail.results;
  const winner = detail.candidates?.find((c) => c.is_selected);

  return (
    <div>
      {/* Header */}
      <Link
        href="/backtest/quant"
        className="mb-3 inline-flex items-center gap-1 text-sm text-gray-400 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Quant Backtests
      </Link>

      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Shield className="h-6 w-6 text-indigo-400" />
            {detail.name || `Quant #${detail.id}`}
          </h1>
          <p className="text-sm text-gray-400">
            {detail.mode === "walk_forward" ? "Walk-Forward" : "Single Split"} |{" "}
            {detail.candidates_count} combos tested |{" "}
            {r ? `${r.folds} fold(s)` : ""}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {detail.stability_score != null && (
            <div className="text-center">
              <div className="text-xs text-gray-500">Stability</div>
              <div className={`text-2xl font-bold ${stabilityColor(detail.stability_score)}`}>
                {fmt(detail.stability_score, 0)}
              </div>
            </div>
          )}
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
      </div>

      {/* Progress */}
      {(detail.status === "running" || detail.status === "pending") && (
        <div className="mb-6 rounded-lg border border-blue-500/30 bg-blue-500/10 p-6 text-center">
          <LoadingSpinner />
          <p className="mt-3 text-blue-300">{detail.progress || "Processing..."}</p>
        </div>
      )}

      {/* Warnings */}
      {detail.warnings && detail.warnings.length > 0 && (
        <div className="mb-6 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
          {detail.warnings.map((w, i) => (
            <div key={i} className="flex items-center gap-2 text-sm text-amber-400">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              {w}
            </div>
          ))}
        </div>
      )}

      {/* Failed */}
      {detail.status === "failed" && detail.diagnostics && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-400">
          {(detail.diagnostics as Record<string, string>).error || "Failed"}
        </div>
      )}

      {/* Completed results */}
      {detail.status === "completed" && r && (
        <>
          {/* Selected Config */}
          {detail.selected_config && (
            <div className="mb-6 rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Trophy className="h-5 w-5 text-amber-400" />
                <h3 className="text-sm font-semibold text-white">
                  Selected Configuration
                </h3>
              </div>
              <div className="flex flex-wrap gap-3 text-sm">
                <ConfigPill
                  label="Min Score"
                  value={detail.selected_config.min_score}
                />
                <ConfigPill
                  label="Target"
                  value={`${detail.selected_config.target_pct}%`}
                />
                <ConfigPill
                  label="Hold Days"
                  value={detail.selected_config.target_days}
                />
                <ConfigPill
                  label="Max DD"
                  value={`${detail.selected_config.max_drawdown_pct}%`}
                />
              </div>
            </div>
          )}

          {/* Train / Val / OOS comparison */}
          <div className="mb-6">
            <h2 className="mb-3 text-lg font-semibold text-white">
              Performance Across Splits
            </h2>
            <div className="overflow-x-auto rounded-lg border border-gray-800">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 bg-gray-900 text-gray-400">
                    <th className="px-3 py-2 text-left">Metric</th>
                    <th className="px-3 py-2 text-right">TRAIN</th>
                    <th className="px-3 py-2 text-right">VALIDATION</th>
                    <th className="px-3 py-2 text-right">OOS</th>
                  </tr>
                </thead>
                <tbody>
                  <MetricRow label="Trades" train={r.train.trades} val={r.val.trades} oos={r.oos.trades} format="int" />
                  <MetricRow label="Win Rate" train={r.train.win_rate} val={r.val.win_rate} oos={r.oos.win_rate} format="pct" />
                  <MetricRow label="Total Return" train={r.train.total_return} val={r.val.total_return} oos={r.oos.total_return} format="pct2" />
                  <MetricRow label="Sharpe" train={r.train.sharpe} val={r.val.sharpe} oos={r.oos.sharpe} />
                  <MetricRow label="Profit Factor" train={r.train.profit_factor} val={r.val.profit_factor} oos={r.oos.profit_factor} />
                  <MetricRow label="Max Drawdown" train={r.train.max_drawdown} val={r.val.max_drawdown} oos={r.oos.max_drawdown} format="pct2" negative />
                  <MetricRow label="Expectancy" train={r.train.expectancy} val={r.val.expectancy} oos={r.oos.expectancy} />
                  <MetricRow label="Avg Hold Days" train={r.train.avg_hold_days} val={r.val.avg_hold_days} oos={r.oos.avg_hold_days} format="f1" />
                  <MetricRow label="Calmar" train={r.train.calmar_ratio} val={r.val.calmar_ratio} oos={r.oos.calmar_ratio} />
                  <MetricRow label="Sortino" train={r.train.sortino} val={r.val.sortino} oos={r.oos.sortino} />
                  <MetricRow label="Exposure %" train={r.train.exposure_pct} val={r.val.exposure_pct} oos={r.oos.exposure_pct} format="f1" />
                </tbody>
              </table>
            </div>
          </div>

          {/* Equity Curve (OOS) */}
          {winner?.equity_curve && winner.equity_curve.length > 0 && (
            <div className="mb-6 rounded-lg border border-gray-800 bg-gray-900 p-4">
              <h2 className="mb-3 text-lg font-semibold text-white">
                OOS Equity Curve
              </h2>
              <EquityChart data={winner.equity_curve} />
            </div>
          )}

          {/* Candidates Table */}
          {detail.candidates && detail.candidates.length > 0 && (
            <div className="mb-6">
              <h2 className="mb-3 text-lg font-semibold text-white">
                Top Candidates (ranked by validation)
              </h2>
              <div className="overflow-x-auto rounded-lg border border-gray-800">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800 bg-gray-900 text-gray-400">
                      <th className="px-3 py-2 text-left">#</th>
                      <th className="px-3 py-2 text-left">Config</th>
                      <th className="px-3 py-2 text-right">Train Obj</th>
                      <th className="px-3 py-2 text-right">Val Obj</th>
                      <th className="px-3 py-2 text-right">Stability</th>
                      <th className="px-3 py-2 text-right">Train WR</th>
                      <th className="px-3 py-2 text-right">Val WR</th>
                      <th className="px-3 py-2 text-right">Train Ret</th>
                      <th className="px-3 py-2 text-right">Val Ret</th>
                      <th className="px-3 py-2">Warnings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.candidates.map((c: QuantCandidate) => (
                      <tr
                        key={c.id}
                        className={`border-b border-gray-800/50 ${
                          c.is_selected ? "bg-indigo-500/10" : "hover:bg-gray-800/30"
                        }`}
                      >
                        <td className="px-3 py-2 text-gray-400">
                          {c.is_selected ? (
                            <Trophy className="h-4 w-4 text-amber-400" />
                          ) : (
                            c.rank
                          )}
                        </td>
                        <td className="px-3 py-2 text-white text-xs font-mono">
                          s{"\u2265"}{c.config.min_score} t={c.config.target_pct}%/{c.config.target_days}d dd={c.config.max_drawdown_pct}%
                        </td>
                        <td className="px-3 py-2 text-right text-gray-300">
                          {fmt(c.train_objective, 4)}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-300">
                          {fmt(c.val_objective, 4)}
                        </td>
                        <td className={`px-3 py-2 text-right font-medium ${stabilityColor(c.stability_score)}`}>
                          {fmt(c.stability_score, 0)}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-300">
                          {c.train_metrics ? pct(c.train_metrics.win_rate) : "\u2014"}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-300">
                          {c.val_metrics ? pct(c.val_metrics.win_rate) : "\u2014"}
                        </td>
                        <td className={`px-3 py-2 text-right ${
                          (c.train_metrics?.total_return ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"
                        }`}>
                          {c.train_metrics ? `${fmt(c.train_metrics.total_return)}%` : "\u2014"}
                        </td>
                        <td className={`px-3 py-2 text-right ${
                          (c.val_metrics?.total_return ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"
                        }`}>
                          {c.val_metrics ? `${fmt(c.val_metrics.total_return)}%` : "\u2014"}
                        </td>
                        <td className="px-3 py-2">
                          {c.warnings && c.warnings.length > 0 && (
                            <span title={c.warnings.join(" | ")}>
                              <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Walk-Forward Fold Details (for selected candidate) */}
          {winner?.fold_metrics && winner.fold_metrics.length > 1 && (
            <div className="mb-6">
              <h2 className="mb-3 text-lg font-semibold text-white">
                Walk-Forward Folds ({winner.fold_metrics.length} folds)
              </h2>
              <div className="overflow-x-auto rounded-lg border border-gray-800">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800 bg-gray-900 text-gray-400">
                      <th className="px-3 py-2 text-left">Fold</th>
                      <th className="px-3 py-2 text-left">Dates</th>
                      <th className="px-3 py-2 text-right">Train WR</th>
                      <th className="px-3 py-2 text-right">Val WR</th>
                      <th className="px-3 py-2 text-right">OOS WR</th>
                      <th className="px-3 py-2 text-right">Train Ret</th>
                      <th className="px-3 py-2 text-right">Val Ret</th>
                      <th className="px-3 py-2 text-right">OOS Ret</th>
                    </tr>
                  </thead>
                  <tbody>
                    {winner.fold_metrics.map((f) => (
                      <tr key={f.fold} className="border-b border-gray-800/50">
                        <td className="px-3 py-2 text-gray-300">#{f.fold + 1}</td>
                        <td className="px-3 py-2 text-xs text-gray-500">
                          {f.dates?.val || ""}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-300">
                          {f.train ? pct(f.train.win_rate) : "\u2014"}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-300">
                          {f.val ? pct(f.val.win_rate) : "\u2014"}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-300">
                          {f.oos ? pct(f.oos.win_rate) : "\u2014"}
                        </td>
                        <td className={`px-3 py-2 text-right ${
                          (f.train?.total_return ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"
                        }`}>
                          {f.train ? `${fmt(f.train.total_return)}%` : "\u2014"}
                        </td>
                        <td className={`px-3 py-2 text-right ${
                          (f.val?.total_return ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"
                        }`}>
                          {f.val ? `${fmt(f.val.total_return)}%` : "\u2014"}
                        </td>
                        <td className={`px-3 py-2 text-right ${
                          (f.oos?.total_return ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"
                        }`}>
                          {f.oos ? `${fmt(f.oos.total_return)}%` : "\u2014"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Config details */}
          <details className="mb-6 rounded-lg border border-gray-800 bg-gray-900">
            <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-white">
              Full Configuration
            </summary>
            <pre className="overflow-x-auto border-t border-gray-800 px-4 py-3 text-xs text-gray-400">
              {JSON.stringify(detail.config, null, 2)}
            </pre>
          </details>
        </>
      )}
    </div>
  );
}

function ConfigPill({ label, value }: { label: string; value: unknown }) {
  return (
    <span className="rounded bg-indigo-500/20 px-2 py-1 text-indigo-300">
      <span className="text-indigo-400/60">{label}:</span>{" "}
      <span className="font-medium">{String(value)}</span>
    </span>
  );
}

function MetricRow({
  label,
  train,
  val,
  oos,
  format,
  negative,
}: {
  label: string;
  train: number | null | undefined;
  val: number | null | undefined;
  oos: number | null | undefined;
  format?: string;
  negative?: boolean;
}) {
  const fmtVal = (v: number | null | undefined) => {
    if (v == null) return "\u2014";
    if (format === "pct") return `${(v * 100).toFixed(1)}%`;
    if (format === "pct2") return `${v.toFixed(2)}%`;
    if (format === "int") return String(Math.round(v));
    if (format === "f1") return v.toFixed(1);
    return v.toFixed(2);
  };

  const color = (v: number | null | undefined) => {
    if (v == null) return "text-gray-500";
    if (negative) return v < 0 ? "text-red-400" : "text-gray-300";
    return v > 0 ? "text-emerald-400" : v < 0 ? "text-red-400" : "text-gray-300";
  };

  return (
    <tr className="border-b border-gray-800/50">
      <td className="px-3 py-2 text-gray-400">{label}</td>
      <td className={`px-3 py-2 text-right ${color(train)}`}>{fmtVal(train)}</td>
      <td className={`px-3 py-2 text-right ${color(val)}`}>{fmtVal(val)}</td>
      <td className={`px-3 py-2 text-right font-medium ${color(oos)}`}>{fmtVal(oos)}</td>
    </tr>
  );
}
