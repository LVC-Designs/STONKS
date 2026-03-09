"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type {
  MLModel,
  MLDashboard,
  MLConfig,
  MLTrainingRun,
  TrainRequest,
} from "@/lib/types";

export function useMLDashboard() {
  return useQuery<MLDashboard>({
    queryKey: ["ml-dashboard"],
    queryFn: async () => {
      const { data } = await api.get("/ml/dashboard");
      return data;
    },
    refetchInterval: 10000,
  });
}

export function useMLModels(modelType?: string, page: number = 1) {
  return useQuery<MLModel[]>({
    queryKey: ["ml-models", modelType, page],
    queryFn: async () => {
      const { data } = await api.get("/ml/models", {
        params: { model_type: modelType, page, page_size: 50 },
      });
      return data;
    },
  });
}

export function useMLModel(id: number | null) {
  return useQuery<MLModel>({
    queryKey: ["ml-model", id],
    queryFn: async () => {
      const { data } = await api.get(`/ml/models/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

export function useMLConfig() {
  return useQuery<MLConfig>({
    queryKey: ["ml-config"],
    queryFn: async () => {
      const { data } = await api.get("/ml/config");
      return data;
    },
  });
}

export function useUpdateMLConfig() {
  const queryClient = useQueryClient();
  return useMutation<MLConfig, Error, { scoring_mode?: string; nn_weight?: number }>({
    mutationFn: async (config) => {
      const { data } = await api.put("/ml/config", config);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml-config"] });
      queryClient.invalidateQueries({ queryKey: ["ml-dashboard"] });
    },
  });
}

export function useTrainModel() {
  const queryClient = useQueryClient();
  return useMutation<{ status: string; model_type: string }, Error, TrainRequest>({
    mutationFn: async (req) => {
      const { data } = await api.post("/ml/train", req);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["ml-models"] });
    },
  });
}

export function useTrainingRuns(page: number = 1) {
  return useQuery<MLTrainingRun[]>({
    queryKey: ["ml-training-runs", page],
    queryFn: async () => {
      const { data } = await api.get("/ml/training", { params: { page } });
      return data;
    },
    refetchInterval: 5000,
  });
}

export function useDeployModel() {
  const queryClient = useQueryClient();
  return useMutation<{ deployed: boolean }, Error, number>({
    mutationFn: async (modelId) => {
      const { data } = await api.post(`/ml/models/${modelId}/deploy`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["ml-models"] });
      queryClient.invalidateQueries({ queryKey: ["ml-config"] });
    },
  });
}

export function useArchiveModel() {
  const queryClient = useQueryClient();
  return useMutation<{ archived: boolean }, Error, number>({
    mutationFn: async (modelId) => {
      const { data } = await api.post(`/ml/models/${modelId}/archive`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["ml-models"] });
    },
  });
}

export function useDeleteModel() {
  const queryClient = useQueryClient();
  return useMutation<{ deleted: boolean }, Error, number>({
    mutationFn: async (modelId) => {
      const { data } = await api.delete(`/ml/models/${modelId}`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["ml-models"] });
    },
  });
}

export function useBackfillOutcomes() {
  return useMutation<
    { message: string; updated: number; outcomes?: Record<string, number> },
    Error,
    { target_pct?: number; target_days?: number; max_drawdown_pct?: number }
  >({
    mutationFn: async (params) => {
      const { data } = await api.post("/ml/backfill-outcomes", null, {
        params,
        timeout: 120000,
      });
      return data;
    },
  });
}
