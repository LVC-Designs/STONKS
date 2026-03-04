"use client";

import { useState } from "react";
import { Eye, EyeOff, Save } from "lucide-react";

interface ApiKeyFormProps {
  polygonKey: string;
  finnhubKey: string;
  onSave: (key: string, value: unknown) => void;
}

export default function ApiKeyForm({
  polygonKey,
  finnhubKey,
  onSave,
}: ApiKeyFormProps) {
  const [polygon, setPolygon] = useState(polygonKey);
  const [finnhub, setFinnhub] = useState(finnhubKey);
  const [showPolygon, setShowPolygon] = useState(false);
  const [showFinnhub, setShowFinnhub] = useState(false);

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
      <h3 className="mb-4 text-lg font-semibold text-white">API Keys</h3>

      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-sm text-gray-400">
            Polygon.io API Key
          </label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type={showPolygon ? "text" : "password"}
                value={polygon}
                onChange={(e) => setPolygon(e.target.value)}
                className="w-full rounded bg-gray-800 px-3 py-2 pr-10 text-sm text-white"
                placeholder="pk_..."
              />
              <button
                type="button"
                onClick={() => setShowPolygon(!showPolygon)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500"
              >
                {showPolygon ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
            <button
              onClick={() => onSave("polygon_api_key", polygon)}
              className="flex items-center gap-1 rounded bg-emerald-600 px-3 py-2 text-sm text-white hover:bg-emerald-500"
            >
              <Save className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm text-gray-400">
            Finnhub API Key
          </label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type={showFinnhub ? "text" : "password"}
                value={finnhub}
                onChange={(e) => setFinnhub(e.target.value)}
                className="w-full rounded bg-gray-800 px-3 py-2 pr-10 text-sm text-white"
                placeholder="..."
              />
              <button
                type="button"
                onClick={() => setShowFinnhub(!showFinnhub)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500"
              >
                {showFinnhub ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
            <button
              onClick={() => onSave("finnhub_api_key", finnhub)}
              className="flex items-center gap-1 rounded bg-emerald-600 px-3 py-2 text-sm text-white hover:bg-emerald-500"
            >
              <Save className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
