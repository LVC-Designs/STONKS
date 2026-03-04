"use client";

import { useState } from "react";
import { Play, Loader2 } from "lucide-react";
import api from "@/lib/api";

const jobs = [
  {
    name: "daily_refresh",
    label: "Daily Refresh",
    description: "Refresh universe, OHLCV, indicators, signals, and news.",
  },
  {
    name: "hourly_refresh",
    label: "Hourly Refresh",
    description: "Refresh top 100 liquid tickers.",
  },
  {
    name: "outcome_tracker",
    label: "Outcome Tracker",
    description: "Evaluate pending signals for success/failure.",
  },
];

export default function JobTrigger() {
  const [running, setRunning] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  const triggerJob = async (jobName: string) => {
    setRunning(jobName);
    setMessage("");
    try {
      const { data } = await api.post(`/jobs/${jobName}/trigger`);
      setMessage(`Job started (ID: ${data.job_run_id})`);
    } catch {
      setMessage("Failed to trigger job. Check that the backend is running.");
    } finally {
      setRunning(null);
    }
  };

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
      <h3 className="mb-4 text-lg font-semibold text-white">Jobs</h3>
      <div className="space-y-3">
        {jobs.map((job) => (
          <div
            key={job.name}
            className="flex items-center justify-between rounded bg-gray-800/50 px-3 py-2"
          >
            <div>
              <p className="text-sm font-medium text-gray-200">{job.label}</p>
              <p className="text-xs text-gray-500">{job.description}</p>
            </div>
            <button
              onClick={() => triggerJob(job.name)}
              disabled={running !== null}
              className="flex items-center gap-1 rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-500 disabled:opacity-50"
            >
              {running === job.name ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run
            </button>
          </div>
        ))}
      </div>
      {message && (
        <p className="mt-3 text-sm text-emerald-400">{message}</p>
      )}
    </div>
  );
}
