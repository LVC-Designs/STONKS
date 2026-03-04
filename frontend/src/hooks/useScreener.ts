"use client";

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { ScreenerResponse } from "@/lib/types";

interface ScreenerParams {
  exchange_group?: string;
  min_score?: number;
  max_score?: number;
  min_volume?: number;
  regime?: string;
  sort_by?: string;
  sort_dir?: string;
  page?: number;
  page_size?: number;
}

export function useScreener(params: ScreenerParams = {}) {
  return useQuery<ScreenerResponse>({
    queryKey: ["screener", params],
    queryFn: async () => {
      const { data } = await api.get("/screener", { params });
      return data;
    },
  });
}
