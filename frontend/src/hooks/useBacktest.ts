"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type {
  BacktestRunListResponse,
  BacktestDetail,
  BacktestSignalListResponse,
  EquityCurvePoint,
  CompareRunSummary,
  BacktestConfig,
  SweepConfig,
  SweepResponse,
} from "@/lib/types";

interface BacktestListParams {
  status?: string;
  sort_by?: string;
  sort_dir?: string;
  page?: number;
  page_size?: number;
}

export function useBacktestRuns(params: BacktestListParams = {}) {
  return useQuery<BacktestRunListResponse>({
    queryKey: ["backtests", params],
    queryFn: async () => {
      const { data } = await api.get("/backtest", { params });
      return data;
    },
    refetchInterval: 5000, // Poll for status updates
  });
}

export function useBacktestDetail(id: number | null) {
  return useQuery<BacktestDetail>({
    queryKey: ["backtest", id],
    queryFn: async () => {
      const { data } = await api.get(`/backtest/${id}`);
      return data;
    },
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "running" ? 3000 : false;
    },
  });
}

export function useBacktestSignals(id: number | null, page: number = 1, pageSize: number = 50) {
  return useQuery<BacktestSignalListResponse>({
    queryKey: ["backtest-signals", id, page, pageSize],
    queryFn: async () => {
      const { data } = await api.get(`/backtest/${id}/signals`, {
        params: { page, page_size: pageSize },
      });
      return data;
    },
    enabled: !!id,
  });
}

export function useBacktestEquity(id: number | null) {
  return useQuery<{ equity_curve: EquityCurvePoint[] }>({
    queryKey: ["backtest-equity", id],
    queryFn: async () => {
      const { data } = await api.get(`/backtest/${id}/equity`);
      return data;
    },
    enabled: !!id,
  });
}

export function useBacktestCompare(ids: number[]) {
  return useQuery<{ runs: CompareRunSummary[] }>({
    queryKey: ["backtest-compare", ids],
    queryFn: async () => {
      const { data } = await api.get("/backtest/compare", {
        params: { ids: ids.join(",") },
      });
      return data;
    },
    enabled: ids.length > 0,
  });
}

export function useCreateBacktest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (config: BacktestConfig) => {
      const { data } = await api.post("/backtest", config);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backtests"] });
    },
  });
}

export function useCreateBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (configs: BacktestConfig[]) => {
      const { data } = await api.post("/backtest/batch", { configs });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backtests"] });
    },
  });
}

export function useSweep() {
  const queryClient = useQueryClient();
  return useMutation<SweepResponse, Error, SweepConfig>({
    mutationFn: async (config: SweepConfig) => {
      const { data } = await api.post("/backtest/sweep", config, {
        timeout: 300000,
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backtests"] });
    },
  });
}

export function useDeleteBacktest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.delete(`/backtest/${id}`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backtests"] });
    },
  });
}
