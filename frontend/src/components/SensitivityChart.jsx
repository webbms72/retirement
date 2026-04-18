import React, { useMemo } from 'react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Cell, ReferenceLine,
} from 'recharts';

const VARIABLE_LABELS = {
  retirement_age: 'Retirement Age (±2yr)',
  annual_spending: 'Annual Spending (±15%)',
  ss_claim_age: 'SS Claim Age (62 vs 70)',
  expected_return_stocks: 'Stock Return (±1%)',
  inflation_rate: 'Inflation (±1%)',
  stock_allocation: 'Stock Allocation (±10%)',
};

export default function SensitivityChart({ sensitivity }) {
  const data = useMemo(() => {
    if (!sensitivity || typeof sensitivity !== 'object') return [];
    return Object.entries(sensitivity)
      .map(([key, delta]) => ({
        key,
        label: VARIABLE_LABELS[key] || key,
        delta: typeof delta === 'number' ? delta : 0,
      }))
      .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
  }, [sensitivity]);

  if (!data.length) {
    return <div style={{ color: '#90a4ae', textAlign: 'center', padding: 32, fontSize: 13 }}>No sensitivity data.</div>;
  }

  const maxAbs = Math.max(...data.map(d => Math.abs(d.delta)), 1);

  return (
    <ResponsiveContainer width="100%" height={Math.max(200, data.length * 44 + 40)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 8, right: 24, bottom: 8, left: 8 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#1e3a5f" horizontal={false} />
        <XAxis
          type="number"
          stroke="#90a4ae"
          tick={{ fill: '#90a4ae', fontSize: 11 }}
          domain={[-maxAbs * 1.1, maxAbs * 1.1]}
          tickFormatter={v => `${v > 0 ? '+' : ''}${(v * 100).toFixed(0)}%`}
        />
        <YAxis
          type="category"
          dataKey="label"
          stroke="#90a4ae"
          tick={{ fill: '#90a4ae', fontSize: 11 }}
          width={180}
        />
        <Tooltip
          contentStyle={{ background: '#0f3460', border: '1px solid #1e3a5f', borderRadius: 8, fontSize: 12 }}
          formatter={(value) => [`${value > 0 ? '+' : ''}${(value * 100).toFixed(1)}% survival`, 'Impact']}
          labelStyle={{ color: '#4fc3f7', fontWeight: 700 }}
        />
        <ReferenceLine x={0} stroke="#90a4ae" />
        <Bar dataKey="delta" radius={[0, 4, 4, 0]}>
          {data.map((entry, index) => (
            <Cell key={index} fill={entry.delta >= 0 ? '#81c784' : '#ef5350'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
