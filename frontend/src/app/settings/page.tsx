"use client";

import { useSettings, useUpdateSetting } from "@/hooks/useSettings";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import ApiKeyForm from "@/components/settings/ApiKeyForm";
import ThresholdConfig from "@/components/settings/ThresholdConfig";
import JobTrigger from "@/components/settings/JobTrigger";

export default function SettingsPage() {
  const { data: settings, isLoading } = useSettings();
  const updateSetting = useUpdateSetting();

  if (isLoading) return <LoadingSpinner />;

  const getValue = (key: string) => {
    const s = settings?.find((s) => s.key === key);
    return s?.value ?? "";
  };

  const handleUpdate = (key: string, value: unknown) => {
    updateSetting.mutate({ key, value });
  };

  return (
    <div className="max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold text-white">Settings</h1>

      <div className="space-y-6">
        <ApiKeyForm
          polygonKey={String(getValue("polygon_api_key"))}
          finnhubKey={String(getValue("finnhub_api_key"))}
          onSave={handleUpdate}
        />

        <ThresholdConfig
          targetPct={Number(getValue("signal_target_pct")) || 5}
          targetDays={Number(getValue("signal_target_days")) || 20}
          maxDrawdown={Number(getValue("signal_max_drawdown_pct")) || -3}
          onSave={handleUpdate}
        />

        <JobTrigger />
      </div>
    </div>
  );
}
