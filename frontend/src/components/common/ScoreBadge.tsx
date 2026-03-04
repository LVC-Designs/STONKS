interface ScoreBadgeProps {
  score: number | null;
  size?: "sm" | "md" | "lg";
}

export default function ScoreBadge({ score, size = "md" }: ScoreBadgeProps) {
  if (score == null) return <span className="text-gray-500">—</span>;

  const color =
    score >= 70
      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
      : score >= 40
        ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
        : "bg-red-500/20 text-red-400 border-red-500/30";

  const sizeClass =
    size === "lg"
      ? "px-3 py-1.5 text-lg font-bold"
      : size === "sm"
        ? "px-1.5 py-0.5 text-xs"
        : "px-2 py-0.5 text-sm font-medium";

  return (
    <span className={`inline-block rounded border ${color} ${sizeClass}`}>
      {score.toFixed(1)}
    </span>
  );
}
