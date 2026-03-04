"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type {
  QuantBacktestListResponse,
  QuantBacktestDetail,
  QuantSweepConfig,
  QuantBacktest,
} from "@/lib/types";

export function useQuantBacktests(page: number = 1, pageSize: number = 20) {
  return useQuery<QuantBacktestListResponse>({
    queryKey: ["quant-backtests", page, pageSize],
    queryFn: async () => {
      const { data } = await api.get("/backtest/quant", {
        params: { page, page_size: pageSize },
      });
      return data;
    },
    refetchInterval: 5000,
  });
}

export function useQuantBacktestDetail(id: number | null) {
  return useQuery<QuantBacktestDetail>({
    queryKey: ["quant-backtest", id],
    queryFn: async () => {
      const { data } = await api.get(`/backtest/quant/${id}`);
      return data;
    },
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "running" ? 3000 : false;
    },
  });
}

export function useCreateQuantSweep() {
  const queryClient = useQueryClient();
  return useMutation<QuantBacktest, Error, QuantSweepConfig>({
    mutationFn: async (config: QuantSweepConfig) => {
      const { data } = await api.post("/backtest/quant", config);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quant-backtests"] });
    },
  });
}

export function useDeleteQuantBacktest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.delete(`/backtest/quant/${id}`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quant-backtests"] });
    },
  });
}
