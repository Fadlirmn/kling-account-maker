"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { idFull } from "@/lib/format";
import { useThemeColors } from "@/lib/theme";
import type { TrendPoint } from "@/lib/api";

// Dibuat = primary (coral, area); Gagal = err putus-putus.
const VARS = ["primary", "err", "text3", "line-soft", "surface-container", "divider", "text", "text2"] as const;

const SERIES = [
  { key: "created", label: "Dibuat", color: "primary" as const, area: true },
  { key: "failed", label: "Gagal", color: "err" as const, area: false },
];

function dayLabel(d: string): string {
  const [, m, day] = d.split("-");
  const bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
  return `${Number(day)} ${bulan[Number(m) - 1] ?? m}`;
}

export function TrendChart({ data }: { data: TrendPoint[] }) {
  const c = useThemeColors(VARS);
  if (!c) return <div className="h-[320px] w-full" aria-hidden="true" />;
  const rows = data.map((p) => ({ ...p, label: dayLabel(p.day) }));
  // sumbu Y: kelipatan 50, minimal 0–50
  const STEP = 50;
  const peak = Math.max(0, ...data.map((p) => Math.max(p.created, p.failed)));
  const top = Math.max(STEP, Math.ceil(peak / STEP) * STEP);
  const ticks = Array.from({ length: top / STEP + 1 }, (_, i) => i * STEP);
  return (
    <div className="h-[320px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 10, right: 12, left: 4, bottom: 4 }}>
          <defs>
            <linearGradient id="primaryFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c.primary} stopOpacity={0.22} />
              <stop offset="100%" stopColor={c.primary} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={c["line-soft"]} vertical={false} />
          <XAxis dataKey="label" tick={{ fill: c.text3, fontSize: 11 }} tickLine={false} axisLine={{ stroke: c.divider }} />
          <YAxis domain={[0, top]} ticks={ticks} interval={0} allowDecimals={false} tick={{ fill: c.text3, fontSize: 11 }} tickLine={false} axisLine={false} width={40} />
          <Tooltip
            contentStyle={{ background: c["surface-container"], border: `1px solid ${c.divider}`, borderRadius: 12, fontSize: 12, color: c.text2 }}
            labelStyle={{ color: c.text, fontWeight: 700 }}
            itemStyle={{ color: c.text2 }}
            formatter={(v: number, name: string) => [idFull(v) + " akun", SERIES.find((s) => s.key === name)?.label ?? name]}
          />
          <Area type="monotone" dataKey="created" stroke={c.primary} strokeWidth={2.5} fill="url(#primaryFill)" dot={false} activeDot={{ r: 4, fill: c.primary }} />
          <Line type="monotone" dataKey="failed" stroke={c.err} strokeWidth={1.75} strokeDasharray="4 4" dot={false} activeDot={{ r: 3, fill: c.err }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TrendLegend() {
  const c = useThemeColors(VARS);
  if (!c) return null;
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-2">
      {SERIES.map((s) => (
        <span key={s.key} className="flex items-center gap-1.5 caption text-text2">
          <span className="inline-block w-3 h-0.5 rounded-full" style={{ background: c[s.color] }} />
          {s.label}
        </span>
      ))}
    </div>
  );
}
