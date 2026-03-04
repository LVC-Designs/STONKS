"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useNewsV2, useRefreshNewsV2, useNewsStats } from "@/hooks/useNews";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import {
  Newspaper,
  RefreshCcw,
  TrendingUp,
  TrendingDown,
  Minus,
  ExternalLink,
  Search,
  ChevronDown,
  BarChart3,
  AlertCircle,
} from "lucide-react";
import type { NewsArticle, NewsRefreshRequest } from "@/lib/types";

const sentimentColors: Record<string, string> = {
  positive: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  negative: "bg-red-500/20 text-red-400 border-red-500/30",
  neutral: "bg-gray-700/50 text-gray-400 border-gray-700",
};

const sentimentIcons: Record<string, React.ReactNode> = {
  positive: <TrendingUp className="h-3.5 w-3.5" />,
  negative: <TrendingDown className="h-3.5 w-3.5" />,
  neutral: <Minus className="h-3.5 w-3.5" />,
};

const DATE_PRESETS = [
  { label: "24h", days: 1 },
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "365d", days: 365 },
];

const SORT_OPTIONS = [
  { value: "newest", label: "Newest First" },
  { value: "oldest", label: "Oldest First" },
  { value: "most_positive", label: "Most Positive" },
  { value: "most_negative", label: "Most Negative" },
  { value: "strongest", label: "Strongest Sentiment" },
];

function formatDate(d: Date): string {
  return d.toISOString().split("T")[0];
}

function formatTime(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return `${Math.floor(diff / 60000)}m ago`;
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString();
}

function formatReturn(ret: number | null) {
  if (ret == null) return "—";
  const color = ret > 0 ? "text-emerald-400" : ret < 0 ? "text-red-400" : "text-gray-400";
  return <span className={color}>{ret > 0 ? "+" : ""}{ret.toFixed(2)}%</span>;
}

export default function NewsPage() {
  const [tickerSearch, setTickerSearch] = useState("");
  const [sentimentFilter, setSentimentFilter] = useState("");
  const [datePreset, setDatePreset] = useState(7);
  const [sortBy, setSortBy] = useState("newest");
  const [page, setPage] = useState(1);
  const [showRefreshMenu, setShowRefreshMenu] = useState(false);

  const startDate = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - datePreset);
    return formatDate(d);
  }, [datePreset]);
  const endDate = useMemo(() => formatDate(new Date()), []);

  const { data, isLoading, error } = useNewsV2({
    ticker: tickerSearch.toUpperCase() || undefined,
    start: startDate,
    end: endDate,
    sentiment: sentimentFilter || undefined,
    sort: sortBy,
    page,
    limit: 50,
  });

  const { data: stats } = useNewsStats({ start: startDate, end: endDate });
  const refreshMutation = useRefreshNewsV2();

  const summary = data?.sentiment_summary;
  const PAGE_SIZE = 50;

  const handleRefresh = (mode: "quick" | "full") => {
    setShowRefreshMenu(false);
    const body: NewsRefreshRequest = {
      mode,
      limit_tickers: mode === "quick" ? 50 : 25,
    };
    refreshMutation.mutate(body);
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Newspaper className="h-6 w-6 text-blue-400" />
            Market News
          </h1>
          <p className="text-sm text-gray-400">
            Incremental news ingestion with sentiment analysis and price context
          </p>
        </div>

        {/* Refresh dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              if (refreshMutation.isPending) return;
              setShowRefreshMenu(!showRefreshMenu);
            }}
            disabled={refreshMutation.isPending}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500 disabled:opacity-50"
          >
            <RefreshCcw
              className={`h-4 w-4 ${refreshMutation.isPending ? "animate-spin" : ""}`}
            />
            {refreshMutation.isPending ? "Fetching..." : "Refresh News"}
            <ChevronDown className="h-3 w-3" />
          </button>

          {showRefreshMenu && (
            <div className="absolute right-0 mt-1 z-10 w-64 rounded-lg border border-gray-700 bg-gray-800 p-2 shadow-xl">
              <button
                onClick={() => handleRefresh("quick")}
                className="w-full rounded px-3 py-2 text-left text-sm text-white hover:bg-gray-700"
              >
                <div className="font-medium">Quick Refresh</div>
                <div className="text-xs text-gray-400">
                  Top 50 tickers by signal score
                </div>
              </button>
              <button
                onClick={() => handleRefresh("full")}
                className="w-full rounded px-3 py-2 text-left text-sm text-white hover:bg-gray-700"
              >
                <div className="font-medium">Full Ingest</div>
                <div className="text-xs text-gray-400">
                  Next batch of all tickers (runs in background)
                </div>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Refresh result */}
      {refreshMutation.isSuccess && refreshMutation.data && (
        <div className="mb-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-400">
          {refreshMutation.data.mode === "quick" ? (
            <>
              Fetched news for {refreshMutation.data.tickers_processed} tickers.{" "}
              {refreshMutation.data.articles_stored} new articles stored.
            </>
          ) : (
            <>Full ingest started for {refreshMutation.data.tickers_queued} tickers (running in background).</>
          )}
        </div>
      )}

      {refreshMutation.isError && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          Failed to refresh: {refreshMutation.error?.message}
        </div>
      )}

      {/* Stats bar */}
      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5">
          <StatCard label="Total Articles" value={String(stats.total_articles)} />
          <SentimentCard
            label="Avg Sentiment"
            value={stats.avg_sentiment != null ? stats.avg_sentiment.toFixed(3) : "—"}
            color={
              stats.avg_sentiment != null
                ? stats.avg_sentiment > 0.05
                  ? "emerald"
                  : stats.avg_sentiment < -0.05
                    ? "red"
                    : "gray"
                : "gray"
            }
          />
          <SentimentCard label="Positive" value={String(stats.positive_count)} color="emerald" />
          <SentimentCard label="Negative" value={String(stats.negative_count)} color="red" />
          <SentimentCard label="Neutral" value={String(stats.neutral_count)} color="gray" />
        </div>
      )}

      {/* Filters bar */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        {/* Ticker search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-2 h-4 w-4 text-gray-500" />
          <input
            type="text"
            placeholder="Ticker..."
            value={tickerSearch}
            onChange={(e) => {
              setTickerSearch(e.target.value);
              setPage(1);
            }}
            className="w-28 rounded-lg border border-gray-700 bg-gray-800 py-1.5 pl-8 pr-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Date range presets */}
        <div className="flex gap-1">
          {DATE_PRESETS.map((p) => (
            <button
              key={p.days}
              onClick={() => {
                setDatePreset(p.days);
                setPage(1);
              }}
              className={`rounded-lg px-3 py-1.5 text-sm ${
                datePreset === p.days
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Sentiment filter */}
        <div className="flex gap-1">
          {["", "positive", "negative", "neutral"].map((s) => (
            <button
              key={s}
              onClick={() => {
                setSentimentFilter(s);
                setPage(1);
              }}
              className={`rounded-lg px-3 py-1.5 text-sm ${
                sentimentFilter === s
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {s || "All"}
            </button>
          ))}
        </div>

        {/* Sort */}
        <select
          value={sortBy}
          onChange={(e) => {
            setSortBy(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* News List */}
      {isLoading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-400">
          Failed to load news. Make sure to click &quot;Refresh News&quot; to fetch from Finnhub.
        </div>
      ) : data && data.items.length > 0 ? (
        <>
          <div className="space-y-3">
            {data.items.map((item: NewsArticle) => (
              <NewsRow key={item.id} item={item} />
            ))}
          </div>

          {/* Pagination */}
          {data.total > PAGE_SIZE && (
            <div className="mt-4 flex items-center justify-between text-sm text-gray-400">
              <span>
                Page {page} of {Math.ceil(data.total / PAGE_SIZE)} ({data.total} articles)
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded bg-gray-800 px-3 py-1 disabled:opacity-50"
                >
                  Prev
                </button>
                <button
                  disabled={page * PAGE_SIZE >= data.total}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded bg-gray-800 px-3 py-1 disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-8 text-center text-gray-400">
          <Newspaper className="mx-auto mb-3 h-10 w-10 text-gray-600" />
          <p className="mb-2 text-lg">No news articles yet</p>
          <p className="mb-4 text-sm">
            Click &quot;Refresh News&quot; to fetch the latest headlines from Finnhub.
          </p>
        </div>
      )}
    </div>
  );
}

function NewsRow({ item }: { item: NewsArticle }) {
  // Get the first ticker context for price display
  const primaryContext = item.ticker_context?.[0] || null;

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 hover:border-gray-700">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          {/* Ticker badges + sentiment + source */}
          <div className="mb-1 flex flex-wrap items-center gap-2">
            {item.tickers.map((t) => (
              <Link
                key={t}
                href={`/ticker/${t}`}
                className="rounded bg-gray-800 px-2 py-0.5 text-xs font-medium text-emerald-400 hover:bg-gray-700"
              >
                {t}
              </Link>
            ))}
            {item.sentiment_label && (
              <span
                className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${
                  sentimentColors[item.sentiment_label] || sentimentColors.neutral
                }`}
              >
                {sentimentIcons[item.sentiment_label]}
                {item.sentiment_label}
                {item.sentiment_score != null && (
                  <span className="ml-1 opacity-70">
                    ({item.sentiment_score.toFixed(2)})
                  </span>
                )}
              </span>
            )}
            <span className="text-xs text-gray-600">
              {item.source} &middot; {formatTime(item.published_at)}
            </span>
          </div>

          <h3 className="text-sm font-medium text-white">{item.headline}</h3>
          {item.summary && (
            <p className="mt-1 text-xs text-gray-400 line-clamp-2">
              {item.summary}
            </p>
          )}

          {/* Price context row */}
          {primaryContext && primaryContext.close_at_publish != null && (
            <div className="mt-2 flex items-center gap-4 text-xs">
              <span className="text-gray-500 flex items-center gap-1">
                <BarChart3 className="h-3 w-3" />
                ${primaryContext.close_at_publish.toFixed(2)}
              </span>
              <span className="text-gray-500">
                1d: {formatReturn(primaryContext.ret_1d)}
              </span>
              <span className="text-gray-500">
                5d: {formatReturn(primaryContext.ret_5d)}
              </span>
              <span className="text-gray-500">
                20d: {formatReturn(primaryContext.ret_20d)}
              </span>
            </div>
          )}
        </div>

        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 text-gray-600 hover:text-blue-400"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        )}
      </div>
    </div>
  );
}

function SentimentCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: "border-emerald-500/30 text-emerald-400",
    red: "border-red-500/30 text-red-400",
    gray: "border-gray-700 text-gray-300",
  };
  return (
    <div className={`rounded-lg border bg-gray-900 p-4 ${colorMap[color] || colorMap.gray}`}>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-xl font-bold">{value}</div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900 p-4 text-gray-300">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-xl font-bold">{value}</div>
    </div>
  );
}
