import React, { useState } from 'react';
import { updateAccount } from '../api/client.js';

export default function NQDCSchedule({ accounts, onAccountsChange }) {
  const nqdcAccounts = accounts.filter(a => a.account_type === 'nqdc');
  const [saving, setSaving] = useState(false);
  if (nqdcAccounts.length === 0) return null;

  async function handleScheduleChange(acctId, newSchedule) {
    setSaving(true);
    try {
      const acct = accounts.find(a => a.id === acctId);
      const updated = await updateAccount(acctId, { ...acct, nqdc_schedule: newSchedule });
      onAccountsChange(prev => prev.map(a => a.id === acctId ? { ...a, ...updated } : a));
    } catch (err) { console.error('Failed to update NQDC schedule:', err); }
    finally { setSaving(false); }
  }

  return (
    <div style={{ marginTop: 24 }}>
      {nqdcAccounts.map(acct => {
        const schedule = Array.isArray(acct.nqdc_schedule) ? acct.nqdc_schedule : [];
        return (
          <div key={acct.id} className="card" style={{ marginBottom: 16 }}>
            <div className="section-title">NQDC Payout Schedule</div>
            <table>
              <thead><tr><th>Date</th><th>Amount ($)</th><th></th></tr></thead>
              <tbody>
                {schedule.map((row, idx) => (
                  <tr key={idx}>
                    <td><input type="date" value={row.date || ''} onChange={e => handleScheduleChange(acct.id, schedule.map((r, i) => i === idx ? { ...r, date: e.target.value } : r))} /></td>
                    <td><input type="number" value={row.amount || ''} onChange={e => handleScheduleChange(acct.id, schedule.map((r, i) => i === idx ? { ...r, amount: parseFloat(e.target.value) || 0 } : r))} style={{ width: 120 }} /></td>
                    <td><button className="danger" onClick={() => handleScheduleChange(acct.id, schedule.filter((_, i) => i !== idx))} disabled={saving}>Remove</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button className="secondary" style={{ marginTop: 10 }} onClick={() => handleScheduleChange(acct.id, [...schedule, { date: '', amount: '' }])} disabled={saving}>+ Add Payout</button>
          </div>
        );
      })}
    </div>
  );
}
