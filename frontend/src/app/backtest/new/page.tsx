"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCreateBacktest, useCreateBatch } from "@/hooks/useBacktest";
import { ArrowLeft, Play, Layers } from "lucide-react";
import Link from "next/link";
import type { BacktestConfig } from "@/lib/types";

export default function NewBacktestPage() {
  const router = useRouter();
  const createMutation = useCreateBacktest();
  const batchMutation = useCreateBatch();

  const [batchMode, setBatchMode] = useState(false);
  const [batchJson, setBatchJson] = useState("");
  const [useCustomWeights, setUseCustomWeights] = useState(false);
  const [useWalkForward, setUseWalkForward] = useState(false);

  const [form, setForm] = useState({
    name: "",
    date_from: "2024-01-01",
    date_to: "2025-12-31",
    min_score: 60,
    target_pct: 5,
    target_days: 20,
    max_drawdown_pct: -3,
    starting_capital: 10000,
    max_positions: 5,
    position_size_pct: 20,
    exchange_group: "US",
    w_trend: 30,
    w_momentum: 25,
    w_volume: 15,
    w_volatility: 10,
    w_structure: 20,
    wf_train: 60,
    wf_validation: 20,
    wf_oos: 20,
  });

  const updateForm = (key: string, value: string | number) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const weightsTotal = form.w_trend + form.w_momentum + form.w_volume + form.w_volatility + form.w_structure;

  const buildConfig = (): BacktestConfig => {
    const config: BacktestConfig = {
      name: form.name || undefined,
      date_from: form.date_from,
      date_to: form.date_to,
      min_score: form.min_score,
      target_pct: form.target_pct,
      target_days: form.target_days,
      max_drawdown_pct: form.max_drawdown_pct,
      portfolio: {
        starting_capital: form.starting_capital,
        max_positions: form.max_positions,
        position_size_pct: form.position_size_pct,
        use_equal_weight: true,
      },
      exchange_groups: [form.exchange_group],
    };

    if (useCustomWeights) {
      config.weights = {
        trend: form.w_trend / 100,
        momentum: form.w_momentum / 100,
        volume: form.w_volume / 100,
        volatility: form.w_volatility / 100,
        structure: form.w_structure / 100,
      };
    }

    if (useWalkForward) {
      config.walk_forward = {
        train_pct: form.wf_train,
        validation_pct: form.wf_validation,
        oos_pct: form.wf_oos,
      };
    }

    return config;
  };

  const handleSubmit = async () => {
    if (batchMode) {
      try {
        const configs = JSON.parse(batchJson);
        await batchMutation.mutateAsync(configs);
        router.push("/backtest");
      } catch {
        alert("Invalid JSON. Provide an array of config objects.");
      }
      return;
    }

    const config = buildConfig();
    await createMutation.mutateAsync(config);
    router.push("/backtest");
  };

  const isSubmitting = createMutation.isPending || batchMutation.isPending;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6">
        <Link
          href="/backtest"
          className="mb-3 inline-flex items-center gap-1 text-sm text-gray-400 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Backtests
        </Link>
        <h1 className="text-2xl font-bold text-white">New Backtest</h1>
        <p className="text-sm text-gray-400">
          Configure a strategy and test it against historical data
        </p>
      </div>

      {/* Batch mode toggle */}
      <div className="mb-4 flex items-center gap-3">
        <button
          onClick={() => setBatchMode(false)}
          className={`rounded-lg px-4 py-2 text-sm ${!batchMode ? "bg-gray-700 text-white" : "bg-gray-800 text-gray-400"}`}
        >
          Single
        </button>
        <button
          onClick={() => setBatchMode(true)}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm ${batchMode ? "bg-gray-700 text-white" : "bg-gray-800 text-gray-400"}`}
        >
          <Layers className="h-4 w-4" />
          Batch Mode
        </button>
      </div>

      {batchMode ? (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-6">
          <p className="mb-3 text-sm text-gray-400">
            Paste a JSON array of config objects. Each will be run as a separate backtest.
          </p>
          <textarea
            value={batchJson}
            onChange={(e) => setBatchJson(e.target.value)}
            rows={16}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 p-3 font-mono text-sm text-gray-200"
            placeholder={`[\n  {\n    "date_from": "2024-01-01",\n    "date_to": "2025-06-30",\n    "min_score": 60,\n    "target_pct": 5,\n    "target_days": 20,\n    "max_drawdown_pct": -3\n  },\n  {\n    "date_from": "2024-01-01",\n    "date_to": "2025-06-30",\n    "min_score": 70,\n    "target_pct": 8,\n    "target_days": 30,\n    "max_drawdown_pct": -5\n  }\n]`}
          />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Basic Settings */}
          <section className="rounded-lg border border-gray-800 bg-gray-900 p-6">
            <h2 className="mb-4 text-lg font-semibold text-white">Basic Settings</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm text-gray-400">Name (optional)</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => updateForm("name", e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                  placeholder="My Strategy"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-400">Exchange Group</label>
                <select
                  value={form.exchange_group}
                  onChange={(e) => updateForm("exchange_group", e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-300"
                >
                  <option value="US">US</option>
                  <option value="CA">Canada</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-400">Date From</label>
                <input
                  type="date"
                  value={form.date_from}
                  onChange={(e) => updateForm("date_from", e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-400">Date To</label>
                <input
                  type="date"
                  value={form.date_to}
                  onChange={(e) => updateForm("date_to", e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                />
              </div>
            </div>
          </section>

          {/* Signal Settings */}
          <section className="rounded-lg border border-gray-800 bg-gray-900 p-6">
            <h2 className="mb-4 text-lg font-semibold text-white">Signal Thresholds</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm text-gray-400">
                  Min Score: {form.min_score}
                </label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={form.min_score}
                  onChange={(e) => updateForm("min_score", Number(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-400">Target %</label>
                <input
                  type="number"
                  value={form.target_pct}
                  onChange={(e) => updateForm("target_pct", Number(e.target.value))}
                  step={0.5}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-400">Target Days</label>
                <input
                  type="number"
                  value={form.target_days}
                  onChange={(e) => updateForm("target_days", Number(e.target.value))}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-400">Max Drawdown %</label>
                <input
                  type="number"
                  value={form.max_drawdown_pct}
                  onChange={(e) => updateForm("max_drawdown_pct", Number(e.target.value))}
                  step={0.5}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                />
              </div>
            </div>
          </section>

          {/* Portfolio Settings */}
          <section className="rounded-lg border border-gray-800 bg-gray-900 p-6">
            <h2 className="mb-4 text-lg font-semibold text-white">Portfolio</h2>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="mb-1 block text-sm text-gray-400">Starting Capital $</label>
                <input
                  type="number"
                  value={form.starting_capital}
                  onChange={(e) => updateForm("starting_capital", Number(e.target.value))}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-400">Max Positions</label>
                <input
                  type="number"
                  value={form.max_positions}
                  onChange={(e) => updateForm("max_positions", Number(e.target.value))}
                  min={1}
                  max={50}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-400">Position Size %</label>
                <input
                  type="number"
                  value={form.position_size_pct}
                  onChange={(e) => updateForm("position_size_pct", Number(e.target.value))}
                  min={1}
                  max={100}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                />
              </div>
            </div>
          </section>

          {/* Custom Weights */}
          <section className="rounded-lg border border-gray-800 bg-gray-900 p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Custom Weights</h2>
              <label className="flex items-center gap-2 text-sm text-gray-400">
                <input
                  type="checkbox"
                  checked={useCustomWeights}
                  onChange={(e) => setUseCustomWeights(e.target.checked)}
                  className="rounded border-gray-600"
                />
                Override default weights
              </label>
            </div>
            {useCustomWeights && (
              <>
                <div className="mb-3 space-y-3">
                  {[
                    { key: "w_trend", label: "Trend" },
                    { key: "w_momentum", label: "Momentum" },
                    { key: "w_volume", label: "Volume" },
                    { key: "w_volatility", label: "Volatility" },
                    { key: "w_structure", label: "Structure" },
                  ].map(({ key, label }) => (
                    <div key={key} className="flex items-center gap-3">
                      <span className="w-24 text-sm text-gray-400">{label}</span>
                      <input
                        type="range"
                        min={0}
                        max={100}
                        value={form[key as keyof typeof form] as number}
                        onChange={(e) => updateForm(key, Number(e.target.value))}
                        className="flex-1"
                      />
                      <span className="w-12 text-right text-sm text-gray-300">
                        {form[key as keyof typeof form] as number}%
                      </span>
                    </div>
                  ))}
                </div>
                <div
                  className={`text-sm font-medium ${
                    weightsTotal === 100 ? "text-emerald-400" : "text-yellow-400"
                  }`}
                >
                  Total: {weightsTotal}%{" "}
                  {weightsTotal !== 100 && "(should be 100%)"}
                </div>
              </>
            )}
          </section>

          {/* Walk-Forward */}
          <section className="rounded-lg border border-gray-800 bg-gray-900 p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Walk-Forward Validation</h2>
              <label className="flex items-center gap-2 text-sm text-gray-400">
                <input
                  type="checkbox"
                  checked={useWalkForward}
                  onChange={(e) => setUseWalkForward(e.target.checked)}
                  className="rounded border-gray-600"
                />
                Enable
              </label>
            </div>
            {useWalkForward && (
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="mb-1 block text-sm text-gray-400">Train %</label>
                  <input
                    type="number"
                    value={form.wf_train}
                    onChange={(e) => updateForm("wf_train", Number(e.target.value))}
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm text-gray-400">Validation %</label>
                  <input
                    type="number"
                    value={form.wf_validation}
                    onChange={(e) => updateForm("wf_validation", Number(e.target.value))}
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm text-gray-400">Out-of-Sample %</label>
                  <input
                    type="number"
                    value={form.wf_oos}
                    onChange={(e) => updateForm("wf_oos", Number(e.target.value))}
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
                  />
                </div>
              </div>
            )}
          </section>
        </div>
      )}

      {/* Submit */}
      <div className="mt-6 flex justify-end">
        <button
          onClick={handleSubmit}
          disabled={isSubmitting}
          className="flex items-center gap-2 rounded-lg bg-emerald-600 px-6 py-3 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          <Play className="h-4 w-4" />
          {isSubmitting ? "Launching..." : batchMode ? "Run Batch" : "Run Backtest"}
        </button>
      </div>
    </div>
  );
}
