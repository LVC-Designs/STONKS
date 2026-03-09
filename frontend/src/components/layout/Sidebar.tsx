"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, FlaskConical, Newspaper, Search, Settings, Shield, TrendingUp } from "lucide-react";

const navItems = [
  { href: "/screener", label: "Screener", icon: Search },
  { href: "/backtest", label: "Backtests", icon: FlaskConical },
  { href: "/backtest/quant", label: "Quant Backtests", icon: Shield },
  { href: "/ml", label: "ML Models", icon: Brain },
  { href: "/news", label: "News", icon: Newspaper },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-56 flex-col border-r border-gray-800 bg-gray-900">
      <div className="flex items-center gap-2 border-b border-gray-800 px-4 py-4">
        <TrendingUp className="h-6 w-6 text-emerald-400" />
        <span className="text-lg font-bold text-white">STONKS</span>
      </div>
      <nav className="flex-1 space-y-1 px-2 py-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          // More specific matching: /backtest/quant should not activate /backtest
          const active =
            pathname === item.href ||
            (pathname.startsWith(item.href + "/") &&
              !navItems.some(
                (other) =>
                  other.href !== item.href &&
                  other.href.startsWith(item.href + "/") &&
                  (pathname === other.href || pathname.startsWith(other.href + "/"))
              ));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                active
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-gray-800 px-4 py-3">
        <p className="text-xs text-gray-500">
          Not financial advice. For educational &amp; research use only.
        </p>
      </div>
    </aside>
  );
}
