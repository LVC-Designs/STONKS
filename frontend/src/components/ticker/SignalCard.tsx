import ScoreBadge from "@/components/common/ScoreBadge";
import type { SignalDetail } from "@/lib/types";

interface SignalCardProps {
  signal: SignalDetail;
}

const subScores = [
  { key: "trend_score", label: "Trend", color: "bg-blue-500" },
  { key: "momentum_score", label: "Momentum", color: "bg-purple-500" },
  { key: "volume_score", label: "Volume", color: "bg-cyan-500" },
  { key: "volatility_score", label: "Volatility", color: "bg-amber-500" },
  { key: "structure_score", label: "Structure", color: "bg-emerald-500" },
] as const;

export default function SignalCard({ signal }: SignalCardProps) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Bullish Signal</h3>
        <ScoreBadge score={signal.score} size="lg" />
      </div>

      <div className="mb-4 flex items-center gap-3 text-sm text-gray-400">
        <span>Date: {signal.signal_date}</span>
        <span
          className={`rounded px-2 py-0.5 text-xs ${
            signal.regime === "strong_trend"
              ? "bg-emerald-500/20 text-emerald-400"
              : signal.regime === "ranging"
                ? "bg-yellow-500/20 text-yellow-400"
                : "bg-blue-500/20 text-blue-400"
          }`}
        >
          {signal.regime}
        </span>
        {signal.outcome && (
          <span
            className={`rounded px-2 py-0.5 text-xs ${
              signal.outcome === "success"
                ? "bg-emerald-500/20 text-emerald-400"
                : signal.outcome === "failure"
                  ? "bg-red-500/20 text-red-400"
                  : "bg-gray-500/20 text-gray-400"
            }`}
          >
            {signal.outcome}
          </span>
        )}
      </div>

      {/* Sub-score bars */}
      <div className="space-y-2">
        {subScores.map(({ key, label, color }) => {
          const val = signal[key] as number | null;
          return (
            <div key={key} className="flex items-center gap-3">
              <span className="w-20 text-xs text-gray-400">{label}</span>
              <div className="flex-1">
                <div className="h-2 overflow-hidden rounded-full bg-gray-800">
                  <div
                    className={`h-full rounded-full ${color}`}
                    style={{ width: `${val ?? 0}%` }}
                  />
                </div>
              </div>
              <span className="w-8 text-right text-xs text-gray-400">
                {val?.toFixed(0) ?? "—"}
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-4 text-xs text-gray-500">
        Target: +{signal.target_pct}% in {signal.target_days} days, max
        drawdown: {signal.max_drawdown_pct}%
      </div>
    </div>
  );
}
