import React, { useMemo } from 'react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts';

const SOURCES = [
  { key: 'ss', label: 'SS', color: '#81c784' },
  { key: '401k_withdrawal', label: '401k', color: '#ff9800' },
  { key: 'roth_withdrawal', label: 'Roth', color: '#4fc3f7' },
  { key: 'brokerage_withdrawal', label: 'Brokerage', color: '#ce93d8' },
  { key: 'nqdc', label: 'NQDC', color: '#ffcc02' },
  { key: 'pension', label: 'Pension', color: '#ff6b6b' },
  { key: 'rental', label: 'Rental', color: '#a5d6a7' },
  { key: 'rmd', label: 'RMD', color: '#ff6b35' },
];

function fmtDollar(v) {
  if (v == null) return '';
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${v}`;
}

export default function IncomeBreakdownChart({ data }) {
  const buckets = useMemo(() => {
    if (!data || data.length === 0) return [];

    // Group into 5-year age buckets
    const bucketMap = {};
    for (const row of data) {
      const age = row.age_you ?? 0;
      const bucketStart = Math.floor(age / 5) * 5;
      const key = `${bucketStart}–${bucketStart + 4}`;
      if (!bucketMap[key]) {
        bucketMap[key] = { label: key, count: 0 };
        for (const s of SOURCES) bucketMap[key][s.key] = 0;
      }
      const src = row.income_by_source || {};
      bucketMap[key].count++;
      bucketMap[key].ss += (src.ss_you || 0) + (src.ss_spouse || 0);
      bucketMap[key]['401k_withdrawal'] += src['401k_withdrawal'] || 0;
      bucketMap[key].roth_withdrawal += src.roth_withdrawal || 0;
      bucketMap[key].brokerage_withdrawal += src.brokerage_withdrawal || 0;
      bucketMap[key].nqdc += src.nqdc || 0;
      bucketMap[key].pension += src.pension || 0;
      bucketMap[key].rental += src.rental || 0;
      bucketMap[key].rmd += src.rmd || 0;
    }

    // Average within each bucket
    return Object.values(bucketMap).map(b => {
      const result = { label: b.label };
      for (const s of SOURCES) result[s.key] = Math.round(b[s.key] / b.count);
      return result;
    });
  }, [data]);

  if (!data || data.length === 0) {
    return <div style={{ color: '#90a4ae', textAlign: 'center', padding: 40 }}>No projection data yet.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={buckets} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e3a5f" />
        <XAxis dataKey="label" stroke="#90a4ae" tick={{ fill: '#90a4ae', fontSize: 11 }} />
        <YAxis stroke="#90a4ae" tick={{ fill: '#90a4ae', fontSize: 11 }} tickFormatter={fmtDollar} width={64} />
        <Tooltip
          contentStyle={{ background: '#0f3460', border: '1px solid #1e3a5f', borderRadius: 8, fontSize: 12 }}
          labelStyle={{ color: '#4fc3f7', fontWeight: 700 }}
          formatter={(value, name) => [fmtDollar(value), name]}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: '#90a4ae' }} />
        {SOURCES.map(s => (
          <Bar key={s.key} dataKey={s.key} name={s.label} stackId="income"
            fill={s.color} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
