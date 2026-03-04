"use client";

import { useRef, useEffect } from "react";
import type { EquityCurvePoint } from "@/lib/types";

interface Props {
  data: EquityCurvePoint[];
  height?: number;
}

export default function EquityChart({ data, height = 350 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    let chart: ReturnType<typeof import("lightweight-charts").createChart> | null = null;

    import("lightweight-charts").then(({ createChart, LineSeries, AreaSeries }) => {
      if (!containerRef.current) return;

      // Clear previous chart
      containerRef.current.innerHTML = "";

      chart = createChart(containerRef.current, {
        height,
        layout: {
          background: { color: "#111827" },
          textColor: "#9CA3AF",
        },
        grid: {
          vertLines: { color: "#1F2937" },
          horzLines: { color: "#1F2937" },
        },
        rightPriceScale: {
          borderColor: "#374151",
        },
        timeScale: {
          borderColor: "#374151",
        },
      });

      const series = chart.addSeries(AreaSeries, {
        lineColor: "#10B981",
        topColor: "rgba(16, 185, 129, 0.3)",
        bottomColor: "rgba(16, 185, 129, 0.02)",
        lineWidth: 2,
        priceFormat: {
          type: "custom",
          formatter: (price: number) => `$${price.toLocaleString()}`,
        },
      });

      series.setData(
        data.map((p) => ({
          time: p.date,
          value: p.equity,
        }))
      );

      chart.timeScale().fitContent();
    });

    return () => {
      chart?.remove();
    };
  }, [data, height]);

  return <div ref={containerRef} />;
}
