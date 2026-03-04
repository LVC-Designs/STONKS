"use client";

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type {
  TickerDetail,
  OHLCVBar,
  SignalDetail,
  IndicatorSet,
  NewsItem,
} from "@/lib/types";

export function useTickerDetail(symbol: string) {
  return useQuery<TickerDetail>({
    queryKey: ["ticker", symbol],
    queryFn: async () => {
      const { data } = await api.get(`/tickers/${symbol}`);
      return data;
    },
    enabled: !!symbol,
  });
}

export function useOHLCV(symbol: string) {
  return useQuery<{ bars: OHLCVBar[]; ticker: string }>({
    queryKey: ["ohlcv", symbol],
    queryFn: async () => {
      const { data } = await api.get(`/tickers/${symbol}/ohlcv`);
      return data;
    },
    enabled: !!symbol,
  });
}

export function useSignals(symbol: string) {
  return useQuery<SignalDetail[]>({
    queryKey: ["signals", symbol],
    queryFn: async () => {
      const { data } = await api.get(`/tickers/${symbol}/signals`, {
        params: { limit: 5 },
      });
      return data;
    },
    enabled: !!symbol,
  });
}

export function useIndicators(symbol: string) {
  return useQuery<IndicatorSet[]>({
    queryKey: ["indicators", symbol],
    queryFn: async () => {
      const { data } = await api.get(`/tickers/${symbol}/indicators`, {
        params: { limit: 1 },
      });
      return data;
    },
    enabled: !!symbol,
  });
}

export function useNews(symbol: string) {
  return useQuery<NewsItem[]>({
    queryKey: ["news", symbol],
    queryFn: async () => {
      const { data } = await api.get(`/tickers/${symbol}/news`);
      return data;
    },
    enabled: !!symbol,
  });
}
