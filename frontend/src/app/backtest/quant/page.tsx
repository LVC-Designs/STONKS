"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useQuantBacktests,
  useCreateQuantSweep,
  useDeleteQuantBacktest,
} from "@/hooks/useQuantBacktest";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import { Zap, Trash2, Shield, AlertTriangle, TrendingUp, ArrowLeft } from "lucide-react";
import type { QuantBacktest, QuantSweepConfig } from "@/lib/types";

const statusColors: Record<string, string> = {
  pending: "bg-yellow-500/20 text-yellow-400",
  running: "bg-blue-500/20 text-blue-400",
  completed: "bg-emerald-500/20 text-emerald-400",
  failed: "bg-red-500/20 text-red-400",
};

function fmt(n: number | null | undefined, d = 2) {
  if (n == null) return "\u2014";
  return n.toFixed(d);
}

function parseCSV(s: string): number[] {
  return s
    .split(",")
    .map((v) => parseFloat(v.trim()))
    .filter((v) => !isNaN(v));
}

export default function QuantBacktestPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuantBacktests(page);
  const createMutation = useCreateQuantSweep();
  const deleteMutation = useDeleteQuantBacktest();

  // Config form state
  const [showForm, setShowForm] = useState(false);
  const [mode, setMode] = useState<"split" | "walk_forward">("split");

  // Split dates
  const [trainFrom, setTrainFrom] = useState("2024-03-01");
  const [trainTo, setTrainTo] = useState("2025-03-01");
  const [valFrom, setValFrom] = useState("2025-03-01");
  const [valTo, setValTo] = useState("2025-09-01");
  const [oosFrom, setOosFrom] = useState("2025-09-01");
  const [oosTo, setOosTo] = useState("2026-03-01");

  // Walk-forward
  const [wfFrom, setWfFrom] = useState("2024-03-01");
  const [wfTo, setWfTo] = useState("2026-03-01");
  const [wfTrain, setWfTrain] = useState(12);
  const [wfVal, setWfVal] = useState(3);
  const [wfOos, setWfOos] = useState(3);
  const [wfStep, setWfStep] = useState(3);

  // Parameter grid
  const [minScoresStr, setMinScoresStr] = useState("40, 50, 60, 70");
  const [targetPctsStr, setTargetPctsStr] = useState("3, 5, 8");
  const [targetDaysStr, setTargetDaysStr] = useState("10, 20, 30");
  const [maxDdStr, setMaxDdStr] = useState("-2, -3, -5");
  const [topK, setTopK] = useState(10);

  const minScores = parseCSV(minScoresStr);
  const targetPcts = parseCSV(targetPctsStr);
  const targetDays = parseCSV(targetDaysStr).map(Math.round);
  const maxDds = parseCSV(maxDdStr);
  const totalCombos =
    minScores.length * targetPcts.length * targetDays.length * maxDds.length;

  const handleLaunch = async () => {
    const config: QuantSweepConfig = {
      mode,
      min_scores: minScores,
      target_pcts: targetPcts,
      target_days_list: targetDays,
      max_drawdown_pcts: maxDds,
      portfolio: {
        starting_capital: 10000,
        max_positions: 5,
        position_size_pct: 20,
      },
      exchange_groups: ["US"],
      top_k: topK,
      objective: "robust_composite",
    };

    if (mode === "split") {
      config.splits = {
        date_from_train: trainFrom,
        date_to_train: trainTo,
        date_from_val: valFrom,
        date_to_val: valTo,
        date_from_oos: oosFrom,
        date_to_oos: oosTo,
      };
    } else {
      config.date_from = wfFrom;
      config.date_to = wfTo;
      config.walk_forward = {
        window_train_months: wfTrain,
        window_val_months: wfVal,
        window_oos_months: wfOos,
        step_months: wfStep,
      };
    }

    await createMutation.mutateAsync(config);
    setShowForm(false);
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <Link
              href="/backtest"
              className="text-sm text-gray-400 hover:text-white"
            >
              <ArrowLeft className="inline h-4 w-4" /> Backtests
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Shield className="h-6 w-6 text-indigo-400" />
            Quant Backtests
          </h1>
          <p className="text-sm text-gray-400">
            Disciplined train/val/OOS framework with anti-overfitting guardrails
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-500"
        >
          <Zap className="h-4 w-4" />
          New Quant Sweep
        </button>
      </div>

      {/* Config Form */}
      {showForm && (
        <div className="mb-6 rounded-lg border border-indigo-500/30 bg-indigo-500/5 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">
            Configure Quant Sweep
          </h2>

          {/* Mode toggle */}
          <div className="mb-4 flex gap-2">
            <button
              onClick={() => setMode("split")}
              className={`rounded-lg px-4 py-2 text-sm ${
                mode === "split"
                  ? "bg-indigo-600 text-white"
                  : "bg-gray-800 text-gray-400"
              }`}
            >
              Single Split
            </button>
            <button
              onClick={() => setMode("walk_forward")}
              className={`rounded-lg px-4 py-2 text-sm ${
                mode === "walk_forward"
                  ? "bg-indigo-600 text-white"
                  : "bg-gray-800 text-gray-400"
              }`}
            >
              Walk-Forward
            </button>
          </div>

          {/* Date inputs */}
          {mode === "split" ? (
            <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-3">
              <DateInput label="Train From" value={trainFrom} onChange={setTrainFrom} />
              <DateInput label="Train To" value={trainTo} onChange={setTrainTo} />
              <DateInput label="Val From" value={valFrom} onChange={setValFrom} />
              <DateInput label="Val To" value={valTo} onChange={setValTo} />
              <DateInput label="OOS From" value={oosFrom} onChange={setOosFrom} />
              <DateInput label="OOS To" value={oosTo} onChange={setOosTo} />
            </div>
          ) : (
            <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
              <DateInput label="Date From" value={wfFrom} onChange={setWfFrom} />
              <DateInput label="Date To" value={wfTo} onChange={setWfTo} />
              <NumInput label="Train (months)" value={wfTrain} onChange={setWfTrain} />
              <NumInput label="Val (months)" value={wfVal} onChange={setWfVal} />
              <NumInput label="OOS (months)" value={wfOos} onChange={setWfOos} />
              <NumInput label="Step (months)" value={wfStep} onChange={setWfStep} />
            </div>
          )}

          {/* Parameter grid */}
          <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
            <TextInput
              label="Min Scores"
              value={minScoresStr}
              onChange={setMinScoresStr}
              hint={`${minScores.length} values`}
            />
            <TextInput
              label="Target %"
              value={targetPctsStr}
              onChange={setTargetPctsStr}
              hint={`${targetPcts.length} values`}
            />
            <TextInput
              label="Holding Days"
              value={targetDaysStr}
              onChange={setTargetDaysStr}
              hint={`${targetDays.length} values`}
            />
            <TextInput
              label="Max Drawdown %"
              value={maxDdStr}
              onChange={setMaxDdStr}
              hint={`${maxDds.length} values`}
            />
          </div>

          <div className="mb-4">
            <NumInput label="Top K (promote to validation)" value={topK} onChange={setTopK} />
          </div>

          {/* Launch */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleLaunch}
              disabled={createMutation.isPending || totalCombos === 0}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              <Zap className="h-4 w-4" />
              {createMutation.isPending
                ? "Launching..."
                : `Launch ${totalCombos} Combos (Top ${topK} to Val)`}
            </button>
            <span className="text-xs text-gray-500">
              {minScores.length} scores &times; {targetPcts.length} targets &times;{" "}
              {targetDays.length} days &times; {maxDds.length} drawdowns
            </span>
            <button
              onClick={() => setShowForm(false)}
              className="ml-auto rounded-lg bg-gray-800 px-4 py-2 text-sm text-gray-400 hover:text-white"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Results list */}
      {isLoading ? (
        <LoadingSpinner />
      ) : data && data.items.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900 text-left text-gray-400">
                <th className="px-3 py-3">Name</th>
                <th className="px-3 py-3">Mode</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3 text-right">Combos</th>
                <th className="px-3 py-3 text-right">Stability</th>
                <th className="px-3 py-3 text-right">OOS Return</th>
                <th className="px-3 py-3 text-right">OOS Sharpe</th>
                <th className="px-3 py-3 text-right">OOS Win Rate</th>
                <th className="px-3 py-3">Warnings</th>
                <th className="px-3 py-3 w-10"></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((qb: QuantBacktest) => {
                const oos = qb.results?.oos;
                return (
                  <tr
                    key={qb.id}
                    className="border-b border-gray-800/50 hover:bg-gray-800/50 cursor-pointer"
                    onClick={() => router.push(`/backtest/quant/${qb.id}`)}
                  >
                    <td className="px-3 py-3 text-white font-medium">
                      {qb.name || `Quant #${qb.id}`}
                      {qb.progress && (
                        <div className="mt-0.5 text-xs text-blue-400">{qb.progress}</div>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      <span className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-300">
                        {qb.mode === "walk_forward" ? "Walk-Forward" : "Split"}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                          statusColors[qb.status] || "bg-gray-700 text-gray-400"
                        }`}
                      >
                        {qb.status}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right text-gray-300">
                      {qb.candidates_count}
                    </td>
                    <td className="px-3 py-3 text-right">
                      {qb.stability_score != null ? (
                        <span
                          className={`font-medium ${
                            qb.stability_score >= 70
                              ? "text-emerald-400"
                              : qb.stability_score >= 40
                                ? "text-yellow-400"
                                : "text-red-400"
                          }`}
                        >
                          {fmt(qb.stability_score, 0)}
                        </span>
                      ) : (
                        "\u2014"
                      )}
                    </td>
                    <td
                      className={`px-3 py-3 text-right font-medium ${
                        oos?.total_return != null
                          ? oos.total_return >= 0
                            ? "text-emerald-400"
                            : "text-red-400"
                          : "text-gray-500"
                      }`}
                    >
                      {oos?.total_return != null ? `${fmt(oos.total_return)}%` : "\u2014"}
                    </td>
                    <td className="px-3 py-3 text-right text-gray-300">
                      {oos ? fmt(oos.sharpe) : "\u2014"}
                    </td>
                    <td className="px-3 py-3 text-right text-gray-300">
                      {oos?.win_rate != null
                        ? `${(oos.win_rate * 100).toFixed(1)}%`
                        : "\u2014"}
                    </td>
                    <td className="px-3 py-3">
                      {qb.warnings && qb.warnings.length > 0 && (
                        <span title={qb.warnings.join(" | ")}>
                          <AlertTriangle className="h-4 w-4 text-amber-400" />
                        </span>
                      )}
                    </td>
                    <td
                      className="px-3 py-3"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm("Delete this quant backtest?")) {
                          deleteMutation.mutate(qb.id);
                        }
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
      ) : (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-8 text-center text-gray-400">
          <Shield className="mx-auto mb-3 h-10 w-10 text-gray-600" />
          <p className="mb-2 text-lg">No quant backtests yet</p>
          <p className="text-sm">
            Launch a disciplined sweep to find robust strategies.
          </p>
        </div>
      )}
    </div>
  );
}

/* Small input components */
function DateInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-gray-400">{label}</label>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
      />
    </div>
  );
}

function NumInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-gray-400">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
      />
    </div>
  );
}

function TextInput({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-gray-400">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
      />
      {hint && <span className="mt-0.5 block text-xs text-gray-500">{hint}</span>}
    </div>
  );
}
