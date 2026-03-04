interface SentimentBadgeProps {
  label: string | null;
  score?: number | null;
}

export default function SentimentBadge({ label, score }: SentimentBadgeProps) {
  if (!label) return <span className="text-gray-500">—</span>;

  const color =
    label === "positive"
      ? "bg-emerald-500/20 text-emerald-400"
      : label === "negative"
        ? "bg-red-500/20 text-red-400"
        : "bg-gray-500/20 text-gray-400";

  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs ${color}`}>
      {label}
      {score != null && ` (${score > 0 ? "+" : ""}${score.toFixed(2)})`}
    </span>
  );
}
