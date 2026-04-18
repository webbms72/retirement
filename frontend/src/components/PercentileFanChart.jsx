import React, { useMemo } from 'react';
import {
  ResponsiveContainer, ComposedChart, Area, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, Legend,
} from 'recharts';

function fmtDollar(v) {
  if (v == null) return '';
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${v}`;
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div style={{
      background: '#0f3460', border: '1px solid #1e3a5f', borderRadius: 8,
      padding: '10px 14px', fontSize: 12,
    }}>
      <div style={{ color: '#4fc3f7', fontWeight: 700, marginBottom: 4 }}>Year {label}</div>
      {payload.map((p, i) => (
        p.value != null && (
          <div key={i} style={{ color: p.color || '#e0e0e0', marginBottom: 2 }}>
            {p.name}: {fmtDollar(Array.isArray(p.value) ? p.value[1] : p.value)}
          </div>
        )
      ))}
    </div>
  );
}

export default function PercentileFanChart({ mcResult, retirementAge, ssStartAge }) {
  const chartData = useMemo(() => {
    if (!mcResult) return [];
    const { percentile_10, percentile_25, percentile_50, percentile_75, percentile_90 } = mcResult;
    if (!percentile_50) return [];

    const years = Object.keys(percentile_50).map(Number).sort((a, b) => a - b);
    return years.map(year => ({
      year,
      p10: percentile_10?.[year] ?? null,
      p25: percentile_25?.[year] ?? null,
      p50: percentile_50?.[year] ?? null,
      p75: percentile_75?.[year] ?? null,
      p90: percentile_90?.[year] ?? null,
      // Area bands as [lower, upper] pairs
      band_90_10: [percentile_10?.[year] ?? null, percentile_90?.[year] ?? null],
      band_75_25: [percentile_25?.[year] ?? null, percentile_75?.[year] ?? null],
    }));
  }, [mcResult]);

  // Find retirement year for reference lines — use first year + retirement offset
  const firstYear = chartData[0]?.year;
  const retirementYear = mcResult?.retirement_year ?? null;
  const ssYear = mcResult?.ss_start_year ?? null;

  if (!chartData.length) {
    return <div style={{ color: '#90a4ae', textAlign: 'center', padding: 40 }}>No Monte Carlo data yet.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={340}>
      <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e3a5f" />
        <XAxis dataKey="year" stroke="#90a4ae" tick={{ fill: '#90a4ae', fontSize: 11 }} />
        <YAxis stroke="#90a4ae" tick={{ fill: '#90a4ae', fontSize: 11 }} tickFormatter={fmtDollar} width={64} />
        <Tooltip content={<CustomTooltip />} />

        {/* Outer band: p10–p90 */}
        <Area
          type="monotone"
          dataKey="p90"
          stroke="none"
          fill="#1a3a5f"
          fillOpacity={0.5}
          name="90th %ile"
          legendType="none"
        />
        <Area
          type="monotone"
          dataKey="p10"
          stroke="none"
          fill="#0d1b2a"
          fillOpacity={1}
          name="10th %ile"
          legendType="none"
        />

        {/* Inner band: p25–p75 */}
        <Area
          type="monotone"
          dataKey="p75"
          stroke="none"
          fill="#1e4a7f"
          fillOpacity={0.6}
          name="75th %ile"
          legendType="none"
        />
        <Area
          type="monotone"
          dataKey="p25"
          stroke="none"
          fill="#0d1b2a"
          fillOpacity={1}
          name="25th %ile"
          legendType="none"
        />

        {/* Median line */}
        <Line
          type="monotone"
          dataKey="p50"
          stroke="#81c784"
          strokeWidth={2.5}
          dot={false}
          name="Median (p50)"
        />

        {/* Boundary lines for visibility */}
        <Line type="monotone" dataKey="p10" stroke="#c62828" strokeWidth={1} dot={false} strokeDasharray="3 3" name="p10" />
        <Line type="monotone" dataKey="p90" stroke="#1565c0" strokeWidth={1} dot={false} strokeDasharray="3 3" name="p90" />

        {retirementYear && (
          <ReferenceLine x={retirementYear} stroke="#ff9800" strokeDasharray="4 3"
            label={{ value: 'Retire', position: 'top', fill: '#ff9800', fontSize: 10 }} />
        )}
        {ssYear && (
          <ReferenceLine x={ssYear} stroke="#81c784" strokeDasharray="4 3"
            label={{ value: 'SS', position: 'insideTopRight', fill: '#81c784', fontSize: 10 }} />
        )}
        <ReferenceLine x={firstYear != null ? firstYear + 73 - (mcResult?.start_age ?? 55) : undefined}
          stroke="#ce93d8" strokeDasharray="4 3"
          label={{ value: 'RMD 73', position: 'top', fill: '#ce93d8', fontSize: 10 }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
