"use client";

import { useState } from "react";
import { Save } from "lucide-react";

interface ThresholdConfigProps {
  targetPct: number;
  targetDays: number;
  maxDrawdown: number;
  onSave: (key: string, value: unknown) => void;
}

export default function ThresholdConfig({
  targetPct,
  targetDays,
  maxDrawdown,
  onSave,
}: ThresholdConfigProps) {
  const [pct, setPct] = useState(targetPct);
  const [days, setDays] = useState(targetDays);
  const [dd, setDd] = useState(maxDrawdown);

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
      <h3 className="mb-4 text-lg font-semibold text-white">
        Signal Prediction Target
      </h3>
      <p className="mb-4 text-xs text-gray-500">
        A signal is considered successful if price rises {">"}= X% within Y
        trading days with max drawdown {"<"}= Z%.
      </p>

      <div className="space-y-4">
        <div className="flex items-end gap-4">
          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Target % (X)
            </label>
            <input
              type="number"
              step="0.5"
              value={pct}
              onChange={(e) => setPct(Number(e.target.value))}
              className="w-24 rounded bg-gray-800 px-3 py-2 text-sm text-white"
            />
          </div>
          <button
            onClick={() => onSave("signal_target_pct", pct)}
            className="rounded bg-emerald-600 p-2 text-white hover:bg-emerald-500"
          >
            <Save className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-end gap-4">
          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Days (Y)
            </label>
            <input
              type="number"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="w-24 rounded bg-gray-800 px-3 py-2 text-sm text-white"
            />
          </div>
          <button
            onClick={() => onSave("signal_target_days", days)}
            className="rounded bg-emerald-600 p-2 text-white hover:bg-emerald-500"
          >
            <Save className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-end gap-4">
          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Max Drawdown % (Z)
            </label>
            <input
              type="number"
              step="0.5"
              value={dd}
              onChange={(e) => setDd(Number(e.target.value))}
              className="w-24 rounded bg-gray-800 px-3 py-2 text-sm text-white"
            />
          </div>
          <button
            onClick={() => onSave("signal_max_drawdown_pct", dd)}
            className="rounded bg-emerald-600 p-2 text-white hover:bg-emerald-500"
          >
            <Save className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
