"use client";

import { useState } from "react";
import {
  useMLDashboard,
  useTrainModel,
  useDeployModel,
  useArchiveModel,
  useDeleteModel,
  useUpdateMLConfig,
  useBackfillOutcomes,
} from "@/hooks/useML";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import {
  Brain,
  Rocket,
  Archive,
  Trash2,
  Play,
  CheckCircle,
  Clock,
  AlertTriangle,
  XCircle,
  Settings2,
  Database,
} from "lucide-react";
import type { MLModel, MLTrainingRun } from "@/lib/types";

const MODEL_TYPE_LABELS: Record<string, string> = {
  signal_scorer: "Signal Scorer",
  pattern_recognizer: "Pattern Recognizer",
  price_predictor: "Price Predictor",
  strategy_selector: "Strategy Selector",
};

const MODEL_TYPE_DESCRIPTIONS: Record<string, string> = {
  signal_scorer: "Feed-forward NN that scores signal quality (win/loss/timeout prediction)",
  pattern_recognizer: "Multi-scale 1D CNN for chart pattern detection",
  price_predictor: "Bi-LSTM with attention for multi-horizon price prediction",
  strategy_selector: "Meta-learner that selects optimal strategy parameters",
};

const statusColors: Record<string, string> = {
  training: "bg-blue-500/20 text-blue-400",
  trained: "bg-emerald-500/20 text-emerald-400",
  deployed: "bg-purple-500/20 text-purple-400",
  archived: "bg-gray-500/20 text-gray-400",
  failed: "bg-red-500/20 text-red-400",
};

const runStatusColors: Record<string, string> = {
  running: "bg-blue-500/20 text-blue-400",
  completed: "bg-emerald-500/20 text-emerald-400",
  failed: "bg-red-500/20 text-red-400",
};

function fmt(n: number | null | undefined, d = 2) {
  if (n == null) return "\u2014";
  return n.toFixed(d);
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "deployed":
      return <Rocket className="h-4 w-4 text-purple-400" />;
    case "trained":
      return <CheckCircle className="h-4 w-4 text-emerald-400" />;
    case "training":
      return <Clock className="h-4 w-4 text-blue-400 animate-spin" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-400" />;
    case "archived":
      return <Archive className="h-4 w-4 text-gray-400" />;
    default:
      return null;
  }
}

export default function MLDashboardPage() {
  const { data: dashboard, isLoading } = useMLDashboard();
  const trainMutation = useTrainModel();
  const deployMutation = useDeployModel();
  const archiveMutation = useArchiveModel();
  const deleteMutation = useDeleteModel();
  const configMutation = useUpdateMLConfig();
  const backfillMutation = useBackfillOutcomes();

  const [showTrainForm, setShowTrainForm] = useState(false);
  const [trainType, setTrainType] = useState("signal_scorer");
  const [trainName, setTrainName] = useState("");
  const [trainDateFrom, setTrainDateFrom] = useState("2024-01-01");
  const [trainDateTo, setTrainDateTo] = useState("2025-12-31");
  const [trainEpochs, setTrainEpochs] = useState(100);
  const [trainLR, setTrainLR] = useState(0.001);
  const [trainHiddenDim, setTrainHiddenDim] = useState(128);
  const [trainDropout, setTrainDropout] = useState(0.3);

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className="p-6 text-gray-400">Failed to load ML dashboard.</div>
    );
  }

  const handleTrain = () => {
    trainMutation.mutate({
      model_type: trainType,
      name: trainName || undefined,
      date_from: trainDateFrom,
      date_to: trainDateTo,
      epochs: trainEpochs,
      lr: trainLR,
      hidden_dim: trainHiddenDim,
      dropout: trainDropout,
    });
    setShowTrainForm(false);
  };

  const handleScoringModeChange = (mode: string) => {
    configMutation.mutate({ scoring_mode: mode });
  };

  const handleNNWeightChange = (weight: number) => {
    configMutation.mutate({ nn_weight: weight });
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Brain className="h-7 w-7 text-purple-400" />
          <h1 className="text-2xl font-bold text-white">ML Models</h1>
          <span className="rounded-full bg-gray-800 px-3 py-1 text-sm text-gray-400">
            {dashboard.total_models} total
          </span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => backfillMutation.mutate({})}
            disabled={backfillMutation.isPending}
            className="flex items-center gap-2 rounded-lg bg-gray-700 px-4 py-2 text-sm font-medium text-white hover:bg-gray-600 disabled:opacity-50 transition"
            title="Label existing signals with win/loss/timeout outcomes using OHLCV data"
          >
            <Database className="h-4 w-4" />
            {backfillMutation.isPending ? "Backfilling..." : "Backfill Outcomes"}
          </button>
          <button
            onClick={() => setShowTrainForm(!showTrainForm)}
            className="flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-500 transition"
          >
            <Play className="h-4 w-4" />
            Train New Model
          </button>
        </div>
      </div>

      {/* Backfill result banner */}
      {backfillMutation.isSuccess && (
        <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-400">
          {backfillMutation.data.message}
          {backfillMutation.data.outcomes && (
            <span className="ml-2 text-emerald-500">
              ({Object.entries(backfillMutation.data.outcomes).map(([k, v]) => `${k}: ${v}`).join(", ")})
            </span>
          )}
        </div>
      )}
      {backfillMutation.isError && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-400">
          Backfill failed: {backfillMutation.error?.message}
        </div>
      )}

      {/* Scoring Config */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
        <div className="flex items-center gap-2 mb-4">
          <Settings2 className="h-5 w-5 text-gray-400" />
          <h2 className="text-lg font-semibold text-white">Scoring Configuration</h2>
        </div>
        <div className="flex flex-wrap items-center gap-6">
          <div>
            <label className="mb-2 block text-sm text-gray-400">Scoring Mode</label>
            <div className="flex gap-2">
              {["rule_based", "ensemble", "nn_only"].map((mode) => (
                <button
                  key={mode}
                  onClick={() => handleScoringModeChange(mode)}
                  className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                    dashboard.scoring_mode === mode
                      ? "bg-purple-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:text-white"
                  }`}
                >
                  {mode === "rule_based" ? "Rule-Based" : mode === "ensemble" ? "Ensemble" : "NN Only"}
                </button>
              ))}
            </div>
          </div>
          {dashboard.scoring_mode === "ensemble" && (
            <div className="min-w-48">
              <label className="mb-2 block text-sm text-gray-400">
                NN Weight: {(dashboard.nn_weight * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0"
                max="100"
                value={dashboard.nn_weight * 100}
                onChange={(e) => handleNNWeightChange(parseInt(e.target.value) / 100)}
                className="w-full accent-purple-500"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>Rule-Based</span>
                <span>NN Only</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Train Form */}
      {showTrainForm && (
        <div className="rounded-xl border border-purple-800/50 bg-gray-900 p-5">
          <h2 className="mb-4 text-lg font-semibold text-white">Train New Model</h2>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div>
              <label className="mb-1 block text-sm text-gray-400">Model Type</label>
              <select
                value={trainType}
                onChange={(e) => setTrainType(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
              >
                {Object.entries(MODEL_TYPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-400">Name (optional)</label>
              <input
                type="text"
                value={trainName}
                onChange={(e) => setTrainName(e.target.value)}
                placeholder="e.g. signal_v2"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-400">Date From</label>
              <input
                type="date"
                value={trainDateFrom}
                onChange={(e) => setTrainDateFrom(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-400">Date To</label>
              <input
                type="date"
                value={trainDateTo}
                onChange={(e) => setTrainDateTo(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-400">Epochs</label>
              <input
                type="number"
                value={trainEpochs}
                onChange={(e) => setTrainEpochs(parseInt(e.target.value))}
                min={5}
                max={500}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-400">Learning Rate</label>
              <input
                type="number"
                value={trainLR}
                onChange={(e) => setTrainLR(parseFloat(e.target.value))}
                step={0.0001}
                min={0.00001}
                max={0.1}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-400">Hidden Dim</label>
              <input
                type="number"
                value={trainHiddenDim}
                onChange={(e) => setTrainHiddenDim(parseInt(e.target.value))}
                min={32}
                max={512}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-400">Dropout</label>
              <input
                type="number"
                value={trainDropout}
                onChange={(e) => setTrainDropout(parseFloat(e.target.value))}
                step={0.05}
                min={0}
                max={0.9}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
              />
            </div>
          </div>
          <div className="mt-4 flex gap-3">
            <button
              onClick={handleTrain}
              disabled={trainMutation.isPending}
              className="rounded-lg bg-purple-600 px-6 py-2 text-sm font-medium text-white hover:bg-purple-500 disabled:opacity-50 transition"
            >
              {trainMutation.isPending ? "Starting..." : "Start Training"}
            </button>
            <button
              onClick={() => setShowTrainForm(false)}
              className="rounded-lg bg-gray-800 px-6 py-2 text-sm text-gray-400 hover:text-white transition"
            >
              Cancel
            </button>
          </div>
          {trainMutation.isSuccess && (
            <p className="mt-3 text-sm text-emerald-400">
              Training started! Check recent runs below for progress.
            </p>
          )}
          {trainMutation.isError && (
            <p className="mt-3 text-sm text-red-400">
              {trainMutation.error?.message || "Failed to start training."}
            </p>
          )}
        </div>
      )}

      {/* Model Type Cards */}
      <div className="grid gap-4 md:grid-cols-2">
        {Object.entries(MODEL_TYPE_LABELS).map(([type, label]) => {
          const activeInfo = dashboard.active_models[type];
          const models = dashboard.models.filter((m) => m.model_type === type);
          return (
            <ModelTypeCard
              key={type}
              type={type}
              label={label}
              description={MODEL_TYPE_DESCRIPTIONS[type]}
              activeInfo={activeInfo}
              models={models}
              onDeploy={(id) => deployMutation.mutate(id)}
              onArchive={(id) => archiveMutation.mutate(id)}
              onDelete={(id) => {
                if (confirm("Delete this model and its artifacts?")) {
                  deleteMutation.mutate(id);
                }
              }}
            />
          );
        })}
      </div>

      {/* Recent Training Runs */}
      {dashboard.recent_training_runs.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <h2 className="mb-4 text-lg font-semibold text-white">Recent Training Runs</h2>
          <div className="space-y-3">
            {dashboard.recent_training_runs.map((run) => (
              <TrainingRunRow key={run.id} run={run} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


function ModelTypeCard({
  type,
  label,
  description,
  activeInfo,
  models,
  onDeploy,
  onArchive,
  onDelete,
}: {
  type: string;
  label: string;
  description: string;
  activeInfo?: { id: number; version: number };
  models: MLModel[];
  onDeploy: (id: number) => void;
  onArchive: (id: number) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-base font-semibold text-white">{label}</h3>
          <p className="text-sm text-gray-500 mt-1">{description}</p>
        </div>
        {activeInfo ? (
          <span className="flex items-center gap-1 rounded-full bg-purple-500/20 px-3 py-1 text-xs text-purple-400">
            <Rocket className="h-3 w-3" />
            v{activeInfo.version} deployed
          </span>
        ) : (
          <span className="rounded-full bg-gray-800 px-3 py-1 text-xs text-gray-500">
            No active model
          </span>
        )}
      </div>

      {models.length === 0 ? (
        <p className="text-sm text-gray-600">No models trained yet.</p>
      ) : (
        <div className="space-y-2">
          {models.map((m) => (
            <div
              key={m.id}
              className="flex items-center justify-between rounded-lg bg-gray-800/50 px-3 py-2"
            >
              <div className="flex items-center gap-3">
                <StatusIcon status={m.status} />
                <div>
                  <span className="text-sm text-white">
                    v{m.version}
                    {m.name ? ` — ${m.name}` : ""}
                  </span>
                  <div className="flex gap-3 text-xs text-gray-500">
                    {m.train_samples && <span>{m.train_samples} samples</span>}
                    {m.training_time_seconds && (
                      <span>{fmt(m.training_time_seconds, 0)}s</span>
                    )}
                    {m.val_metrics && (
                      <span>
                        val acc: {fmt((m.val_metrics as Record<string, number>).accuracy * 100, 1)}%
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex gap-1">
                {m.status === "trained" && (
                  <button
                    onClick={() => onDeploy(m.id)}
                    title="Deploy"
                    className="rounded p-1.5 text-gray-500 hover:bg-gray-700 hover:text-purple-400 transition"
                  >
                    <Rocket className="h-4 w-4" />
                  </button>
                )}
                {m.status !== "archived" && m.status !== "training" && (
                  <button
                    onClick={() => onArchive(m.id)}
                    title="Archive"
                    className="rounded p-1.5 text-gray-500 hover:bg-gray-700 hover:text-yellow-400 transition"
                  >
                    <Archive className="h-4 w-4" />
                  </button>
                )}
                <button
                  onClick={() => onDelete(m.id)}
                  title="Delete"
                  className="rounded p-1.5 text-gray-500 hover:bg-gray-700 hover:text-red-400 transition"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


function TrainingRunRow({ run }: { run: MLTrainingRun }) {
  const progress = run.current_epoch && run.total_epochs
    ? Math.round((run.current_epoch / run.total_epochs) * 100)
    : null;

  return (
    <div className="flex items-center justify-between rounded-lg bg-gray-800/50 px-4 py-3">
      <div className="flex items-center gap-3">
        <span className={`rounded-full px-2 py-0.5 text-xs ${runStatusColors[run.status] || "bg-gray-700 text-gray-400"}`}>
          {run.status}
        </span>
        <span className="text-sm text-white">
          Run #{run.id}
          {run.ml_model_id ? ` (Model #${run.ml_model_id})` : ""}
        </span>
      </div>
      <div className="flex items-center gap-4">
        {run.status === "running" && progress != null && (
          <div className="flex items-center gap-2">
            <div className="h-2 w-24 overflow-hidden rounded-full bg-gray-700">
              <div
                className="h-full bg-purple-500 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-xs text-gray-400">
              {run.current_epoch}/{run.total_epochs}
            </span>
          </div>
        )}
        {run.best_val_loss != null && (
          <span className="text-xs text-gray-500">
            best val loss: {fmt(run.best_val_loss, 4)}
          </span>
        )}
        {run.error_message && (
          <span className="flex items-center gap-1 text-xs text-red-400" title={run.error_message}>
            <AlertTriangle className="h-3 w-3" />
            Error
          </span>
        )}
        {run.started_at && (
          <span className="text-xs text-gray-600">
            {new Date(run.started_at).toLocaleDateString()}
          </span>
        )}
      </div>
    </div>
  );
}
