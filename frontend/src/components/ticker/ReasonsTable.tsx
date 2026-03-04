import type { ReasonItem } from "@/lib/types";

interface ReasonsTableProps {
  reasons: ReasonItem[];
}

const componentColors: Record<string, string> = {
  trend: "bg-blue-500/20 text-blue-400",
  momentum: "bg-purple-500/20 text-purple-400",
  volume: "bg-cyan-500/20 text-cyan-400",
  volatility: "bg-amber-500/20 text-amber-400",
  structure: "bg-emerald-500/20 text-emerald-400",
};

export default function ReasonsTable({ reasons }: ReasonsTableProps) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
      <h3 className="mb-3 text-lg font-semibold text-white">
        Why Bullish
      </h3>
      <div className="space-y-2">
        {reasons.map((r, i) => (
          <div
            key={i}
            className="flex items-start gap-3 rounded bg-gray-800/50 px-3 py-2"
          >
            <span
              className={`mt-0.5 rounded px-2 py-0.5 text-xs ${
                componentColors[r.component] || "bg-gray-500/20 text-gray-400"
              }`}
            >
              {r.component}
            </span>
            <span className="flex-1 text-sm text-gray-300">{r.reason}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
