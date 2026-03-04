"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type {
  MarketNewsResponse,
  NewsListResponse,
  NewsRefreshRequest,
  NewsRefreshResponse,
  NewsStatsResponse,
} from "@/lib/types";

interface NewsParams {
  ticker?: string;
  start?: string;
  end?: string;
  sentiment?: string;
  min_abs_sentiment?: number;
  sort?: string;
  limit?: number;
  page?: number;
}

// V2 endpoint: GET /api/news
export function useNewsV2(params: NewsParams = {}) {
  return useQuery<NewsListResponse>({
    queryKey: ["news-v2", params],
    queryFn: async () => {
      const { data } = await api.get("/news", { params });
      return data;
    },
  });
}

// Backward-compatible: GET /api/news/market
export function useMarketNews(params: Omit<NewsParams, "ticker" | "sort" | "min_abs_sentiment"> = {}) {
  return useQuery<MarketNewsResponse>({
    queryKey: ["market-news", params],
    queryFn: async () => {
      const { data } = await api.get("/news/market", { params });
      return data;
    },
  });
}

// V2 refresh: POST /api/news/refresh with JSON body
export function useRefreshNewsV2() {
  const queryClient = useQueryClient();
  return useMutation<NewsRefreshResponse, Error, NewsRefreshRequest>({
    mutationFn: async (body) => {
      const { data } = await api.post("/news/refresh", body, {
        timeout: 120000, // 2 min for quick, full returns immediately
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["news-v2"] });
      queryClient.invalidateQueries({ queryKey: ["market-news"] });
      queryClient.invalidateQueries({ queryKey: ["news-stats"] });
    },
  });
}

// Backward-compatible refresh (for existing code that calls useRefreshNews)
export function useRefreshNews() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (limit: number = 10) => {
      const { data } = await api.post("/news/refresh", {
        mode: "quick",
        limit_tickers: limit,
      }, {
        timeout: 120000,
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["market-news"] });
      queryClient.invalidateQueries({ queryKey: ["news-v2"] });
      queryClient.invalidateQueries({ queryKey: ["news-stats"] });
    },
  });
}

// GET /api/news/stats
export function useNewsStats(params: { start?: string; end?: string } = {}) {
  return useQuery<NewsStatsResponse>({
    queryKey: ["news-stats", params],
    queryFn: async () => {
      const { data } = await api.get("/news/stats", { params });
      return data;
    },
  });
}
