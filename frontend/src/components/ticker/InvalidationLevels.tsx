interface InvalidationLevelsProps {
  invalidation: {
    levels: { price: number; reason: string }[];
    stop_atr_multiple: number;
  };
}

export default function InvalidationLevels({
  invalidation,
}: InvalidationLevelsProps) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
      <h3 className="mb-3 text-lg font-semibold text-white">
        Invalidation Levels
      </h3>
      <div className="space-y-1">
        {invalidation.levels.map((level, i) => (
          <div
            key={i}
            className="flex items-center justify-between rounded bg-gray-800/50 px-3 py-2 text-sm"
          >
            <span className="text-red-400">${level.price.toFixed(2)}</span>
            <span className="text-gray-400">{level.reason}</span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-gray-500">
        ATR stop multiple: {invalidation.stop_atr_multiple}x
      </p>
    </div>
  );
}
