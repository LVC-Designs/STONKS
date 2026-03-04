"use client";

import { useState } from "react";
import type { IndicatorSet } from "@/lib/types";
import { formatNumber } from "@/lib/formatters";

interface IndicatorPanelProps {
  indicators: IndicatorSet;
}

type Tab = "trend" | "momentum" | "volume" | "volatility" | "ichimoku";

const tabs: { key: Tab; label: string }[] = [
  { key: "trend", label: "Trend" },
  { key: "momentum", label: "Momentum" },
  { key: "volume", label: "Volume" },
  { key: "volatility", label: "Volatility" },
  { key: "ichimoku", label: "Ichimoku" },
];

export default function IndicatorPanel({ indicators }: IndicatorPanelProps) {
  const [activeTab, setActiveTab] = useState<Tab>("trend");

  const renderRow = (label: string, value: number | null | undefined) => (
    <div className="flex justify-between py-1 text-sm">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-200">
        {value != null ? formatNumber(value, 2) : "—"}
      </span>
    </div>
  );

  const content: Record<Tab, React.ReactNode> = {
    trend: (
      <>
        {renderRow("SMA 50", indicators.sma_50)}
        {renderRow("SMA 100", indicators.sma_100)}
        {renderRow("SMA 200", indicators.sma_200)}
        {renderRow("EMA 9", indicators.ema_9)}
        {renderRow("EMA 20", indicators.ema_20)}
        {renderRow("EMA 50", indicators.ema_50)}
      </>
    ),
    momentum: (
      <>
        {renderRow("RSI (14)", indicators.rsi_14)}
        {renderRow("MACD Line", indicators.macd_line)}
        {renderRow("MACD Signal", indicators.macd_signal)}
        {renderRow("MACD Histogram", indicators.macd_histogram)}
        {renderRow("Stochastic %K", indicators.stoch_k)}
        {renderRow("Stochastic %D", indicators.stoch_d)}
        {renderRow("ROC (12)", indicators.roc_12)}
        {renderRow("CCI (20)", indicators.cci_20)}
        {renderRow("ADX (14)", indicators.adx_14)}
        {renderRow("+DI", indicators.plus_di)}
        {renderRow("-DI", indicators.minus_di)}
      </>
    ),
    volume: (
      <>
        {renderRow("OBV", indicators.obv)}
        {renderRow("Volume SMA (20)", indicators.volume_sma_20)}
        {renderRow("Volume Ratio", indicators.volume_ratio)}
        {renderRow("OBV Slope", indicators.obv_slope)}
      </>
    ),
    volatility: (
      <>
        {renderRow("BB Upper", indicators.bb_upper)}
        {renderRow("BB Middle", indicators.bb_middle)}
        {renderRow("BB Lower", indicators.bb_lower)}
        {renderRow("BB Width", indicators.bb_width)}
        {renderRow("BB %B", indicators.bb_pctb)}
        {renderRow("ATR (14)", indicators.atr_14)}
        {renderRow("ATR Percentile", indicators.atr_percentile)}
      </>
    ),
    ichimoku: (
      <>
        {renderRow("Tenkan-sen (9)", indicators.ichi_tenkan)}
        {renderRow("Kijun-sen (26)", indicators.ichi_kijun)}
        {renderRow("Senkou Span A", indicators.ichi_senkou_a)}
        {renderRow("Senkou Span B", indicators.ichi_senkou_b)}
        {renderRow("Chikou Span", indicators.ichi_chikou)}
        <div className="mt-3 border-t border-gray-800 pt-3">
          <p className="mb-1 text-xs font-medium text-gray-400">Fibonacci</p>
          {renderRow("Swing High", indicators.fib_swing_high)}
          {renderRow("Swing Low", indicators.fib_swing_low)}
          {renderRow("23.6%", indicators.fib_236)}
          {renderRow("38.2%", indicators.fib_382)}
          {renderRow("50.0%", indicators.fib_500)}
          {renderRow("61.8%", indicators.fib_618)}
          {renderRow("78.6%", indicators.fib_786)}
        </div>
      </>
    ),
  };

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
      <h3 className="mb-3 text-lg font-semibold text-white">Indicators</h3>
      <div className="mb-3 flex gap-1">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`rounded px-3 py-1 text-xs font-medium transition ${
              activeTab === tab.key
                ? "bg-gray-700 text-white"
                : "text-gray-400 hover:bg-gray-800 hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="divide-y divide-gray-800/50">{content[activeTab]}</div>
    </div>
  );
}
