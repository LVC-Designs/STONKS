"use client";

import Link from "next/link";
import type { ScreenerRow } from "@/lib/types";
import ScoreBadge from "@/components/common/ScoreBadge";
import { formatDate } from "@/lib/formatters";
import { ChevronUp, ChevronDown } from "lucide-react";

interface ScreenerTableProps {
  items: ScreenerRow[];
  sortBy: string;
  sortDir: "asc" | "desc";
  onSort: (column: string) => void;
}

const columns = [
  { key: "symbol", label: "Symbol" },
  { key: "name", label: "Name" },
  { key: "exchange", label: "Exchange" },
  { key: "score", label: "Score" },
  { key: "regime", label: "Regime" },
  { key: "trend_score", label: "Trend" },
  { key: "momentum_score", label: "Momentum" },
  { key: "volume_score", label: "Volume" },
  { key: "volatility_score", label: "Volatility" },
  { key: "structure_score", label: "Structure" },
  { key: "signal_date", label: "Signal Date" },
];

export default function ScreenerTable({
  items,
  sortBy,
  sortDir,
  onSort,
}: ScreenerTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-800">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-gray-800 bg-gray-900 text-xs text-gray-400">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => onSort(col.key)}
                className="cursor-pointer whitespace-nowrap px-4 py-3 hover:text-white"
              >
                <div className="flex items-center gap-1">
                  {col.label}
                  {sortBy === col.key &&
                    (sortDir === "desc" ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronUp className="h-3 w-3" />
                    ))}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {items.map((row) => (
            <tr
              key={row.symbol}
              className="hover:bg-gray-800/50 transition"
            >
              <td className="px-4 py-3">
                <Link
                  href={`/ticker/${row.symbol}`}
                  className="font-medium text-emerald-400 hover:underline"
                >
                  {row.symbol}
                </Link>
              </td>
              <td className="max-w-[200px] truncate px-4 py-3 text-gray-300">
                {row.name || "—"}
              </td>
              <td className="px-4 py-3 text-gray-400">{row.exchange || "—"}</td>
              <td className="px-4 py-3">
                <ScoreBadge score={row.score} />
              </td>
              <td className="px-4 py-3">
                <span
                  className={`rounded px-2 py-0.5 text-xs ${
                    row.regime === "strong_trend"
                      ? "bg-emerald-500/20 text-emerald-400"
                      : row.regime === "ranging"
                        ? "bg-yellow-500/20 text-yellow-400"
                        : "bg-blue-500/20 text-blue-400"
                  }`}
                >
                  {row.regime || "—"}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-300">
                {row.trend_score?.toFixed(0) ?? "—"}
              </td>
              <td className="px-4 py-3 text-gray-300">
                {row.momentum_score?.toFixed(0) ?? "—"}
              </td>
              <td className="px-4 py-3 text-gray-300">
                {row.volume_score?.toFixed(0) ?? "—"}
              </td>
              <td className="px-4 py-3 text-gray-300">
                {row.volatility_score?.toFixed(0) ?? "—"}
              </td>
              <td className="px-4 py-3 text-gray-300">
                {row.structure_score?.toFixed(0) ?? "—"}
              </td>
              <td className="px-4 py-3 text-gray-400">
                {formatDate(row.signal_date)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
