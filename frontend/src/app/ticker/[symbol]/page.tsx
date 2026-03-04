"use client";

import { use } from "react";
import {
  useTickerDetail,
  useOHLCV,
  useSignals,
  useNews,
} from "@/hooks/useTickerDetail";
import PriceChart from "@/components/ticker/PriceChart";
import SignalCard from "@/components/ticker/SignalCard";
import ReasonsTable from "@/components/ticker/ReasonsTable";
import InvalidationLevels from "@/components/ticker/InvalidationLevels";
import IndicatorPanel from "@/components/ticker/IndicatorPanel";
import NewsPanel from "@/components/ticker/NewsPanel";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function TickerPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol } = use(params);
  const upperSymbol = symbol.toUpperCase();

  const { data: tickerData, isLoading: tickerLoading } =
    useTickerDetail(upperSymbol);
  const { data: ohlcvData, isLoading: ohlcvLoading } = useOHLCV(upperSymbol);
  const { data: signals } = useSignals(upperSymbol);
  const { data: news } = useNews(upperSymbol);

  if (tickerLoading) return <LoadingSpinner />;

  if (!tickerData) {
    return (
      <div className="text-center text-gray-400">
        <p className="text-lg">Ticker not found: {upperSymbol}</p>
        <Link
          href="/screener"
          className="mt-4 inline-block text-emerald-400 hover:underline"
        >
          Back to screener
        </Link>
      </div>
    );
  }

  const { ticker, latest_signal, latest_indicators } = tickerData;

  return (
    <div>
      <Link
        href="/screener"
        className="mb-4 inline-flex items-center gap-1 text-sm text-gray-400 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Screener
      </Link>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white">{ticker.symbol}</h1>
        <p className="text-gray-400">
          {ticker.name} &middot; {ticker.exchange} &middot; {ticker.country}
        </p>
      </div>

      {/* Chart */}
      <div className="mb-6 rounded-lg border border-gray-800 bg-gray-900 p-4">
        {ohlcvLoading ? (
          <LoadingSpinner />
        ) : ohlcvData && ohlcvData.bars.length > 0 ? (
          <PriceChart
            bars={ohlcvData.bars}
            sma50={latest_indicators?.sma_50 ?? undefined}
            sma200={latest_indicators?.sma_200 ?? undefined}
          />
        ) : (
          <p className="py-8 text-center text-gray-500">
            No OHLCV data available
          </p>
        )}
      </div>

      {/* Main content grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left column: Signal + Reasons */}
        <div className="space-y-6">
          {latest_signal && <SignalCard signal={latest_signal} />}

          {latest_signal?.reasons && latest_signal.reasons.length > 0 && (
            <ReasonsTable reasons={latest_signal.reasons} />
          )}

          {latest_signal?.invalidation && (
            <InvalidationLevels invalidation={latest_signal.invalidation} />
          )}
        </div>

        {/* Right column: Indicators + News */}
        <div className="space-y-6">
          {latest_indicators && (
            <IndicatorPanel indicators={latest_indicators} />
          )}

          <NewsPanel news={news || []} />
        </div>
      </div>

      <p className="mt-6 text-xs text-gray-600">
        Disclaimer: This tool provides probabilistic scoring for educational and
        research purposes only. It does not constitute financial advice. Past
        performance does not guarantee future results.
      </p>
    </div>
  );
}
