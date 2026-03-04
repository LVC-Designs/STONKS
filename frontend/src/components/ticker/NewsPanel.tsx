import type { NewsItem } from "@/lib/types";
import SentimentBadge from "@/components/common/SentimentBadge";
import { formatRelativeTime } from "@/lib/formatters";
import { ExternalLink } from "lucide-react";

interface NewsPanelProps {
  news: NewsItem[];
}

export default function NewsPanel({ news }: NewsPanelProps) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
      <h3 className="mb-3 text-lg font-semibold text-white">Recent News</h3>
      {news.length === 0 ? (
        <p className="text-sm text-gray-500">No recent news available</p>
      ) : (
        <div className="space-y-3">
          {news.slice(0, 10).map((item) => (
            <div
              key={item.id}
              className="rounded bg-gray-800/50 px-3 py-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  {item.url ? (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-gray-200 hover:text-white"
                    >
                      {item.headline}
                      <ExternalLink className="ml-1 inline h-3 w-3 text-gray-500" />
                    </a>
                  ) : (
                    <p className="text-sm font-medium text-gray-200">
                      {item.headline}
                    </p>
                  )}
                  <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
                    <span>{item.source}</span>
                    <span>&middot;</span>
                    <span>{formatRelativeTime(item.published_at)}</span>
                  </div>
                </div>
                <SentimentBadge
                  label={item.sentiment_label}
                  score={item.sentiment_score}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
