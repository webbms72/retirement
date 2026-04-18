import React from 'react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, Legend,
} from 'recharts';

function fmtDollar(v) {
  if (v == null) return '';
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${v}`;
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: '#0f3460', border: '1px solid #1e3a5f', borderRadius: 8,
      padding: '10px 14px', fontSize: 12,
    }}>
      <div style={{ color: '#4fc3f7', fontWeight: 700, marginBottom: 4 }}>Age {d.age_you} ({d.year})</div>
      <div style={{ color: '#e0e0e0' }}>Portfolio: {fmtDollar(d.portfolio_balance)}</div>
    </div>
  );
}

export default function PortfolioChart({ data, retirementAge, ssStartAge }) {
  if (!data || data.length === 0) {
    return <div style={{ color: '#90a4ae', textAlign: 'center', padding: 40 }}>No projection data yet.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e3a5f" />
        <XAxis
          dataKey="age_you"
          stroke="#90a4ae"
          tick={{ fill: '#90a4ae', fontSize: 11 }}
          label={{ value: 'Age', position: 'insideBottomRight', offset: -4, fill: '#90a4ae', fontSize: 11 }}
        />
        <YAxis
          stroke="#90a4ae"
          tick={{ fill: '#90a4ae', fontSize: 11 }}
          tickFormatter={fmtDollar}
          width={64}
        />
        <Tooltip content={<CustomTooltip />} />
        <Line
          type="monotone"
          dataKey="portfolio_balance"
          stroke="#4fc3f7"
          strokeWidth={2}
          dot={false}
          name="Portfolio Balance"
        />
        {retirementAge != null && (
          <ReferenceLine x={retirementAge} stroke="#ff9800" strokeDasharray="4 3"
            label={{ value: 'Retire', position: 'top', fill: '#ff9800', fontSize: 10 }} />
        )}
        {ssStartAge != null && (
          <ReferenceLine x={ssStartAge} stroke="#81c784" strokeDasharray="4 3"
            label={{ value: 'SS', position: 'top', fill: '#81c784', fontSize: 10 }} />
        )}
        <ReferenceLine x={73} stroke="#ce93d8" strokeDasharray="4 3"
          label={{ value: 'RMD', position: 'top', fill: '#ce93d8', fontSize: 10 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
