import React, { useEffect, useState } from 'react';
import { getAccounts, createAccount, updateAccount, deleteAccount } from '../api/client.js';

const TYPE_COLORS = {
  '401k': '#ff9800', roth_ira: '#4fc3f7', brokerage: '#ce93d8',
  hsa: '#81c784', nqdc: '#ffcc02', pension: '#ff6b6b', real_estate: '#a5d6a7',
};
const TYPE_LABELS = {
  '401k': '401k', roth_ira: 'Roth IRA', brokerage: 'Brokerage',
  hsa: 'HSA', nqdc: 'NQDC', pension: 'Pension', real_estate: 'Real Estate',
};
const ACCOUNT_TYPES = Object.keys(TYPE_LABELS);

function TypeBadge({ type }) {
  const color = TYPE_COLORS[type] || '#90a4ae';
  return (
    <span className="badge" style={{ background: color + '22', color, border: `1px solid ${color}55` }}>
      {TYPE_LABELS[type] || type}
    </span>
  );
}

const EMPTY_FORM = { account_type: '401k', owner_id: '', balance: '', annual_return: '', annual_contribution: '' };

export default function AccountsTable({ accounts, profiles, onAccountsChange }) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getAccounts().then(onAccountsChange).catch(err => console.error('Failed to load accounts:', err));
  }, []);

  async function handleAdd() {
    if (!form.owner_id) return;
    setSaving(true);
    try {
      const created = await createAccount({
        account_type: form.account_type,
        owner_id: parseInt(form.owner_id, 10),
        balance: parseFloat(form.balance) || 0,
        annual_return: parseFloat(form.annual_return) || 0,
        annual_contribution: parseFloat(form.annual_contribution) || 0,
      });
      onAccountsChange(prev => [...prev, created]);
      setForm(EMPTY_FORM);
      setShowAddForm(false);
    } catch (err) { console.error('Create account failed:', err); }
    finally { setSaving(false); }
  }

  async function handleSaveEdit(id) {
    setSaving(true);
    try {
      const acct = accounts.find(a => a.id === id);
      const updated = await updateAccount(id, {
        ...acct,
        balance: parseFloat(editForm.balance) || 0,
        annual_return: parseFloat(editForm.annual_return) || 0,
        annual_contribution: parseFloat(editForm.annual_contribution) || 0,
      });
      onAccountsChange(prev => prev.map(a => a.id === id ? { ...a, ...updated } : a));
      setEditingId(null);
    } catch (err) { console.error('Update account failed:', err); }
    finally { setSaving(false); }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this account?')) return;
    try {
      await deleteAccount(id);
      onAccountsChange(prev => prev.filter(a => a.id !== id));
    } catch (err) { console.error('Delete account failed:', err); }
  }

  const ownerLabel = id => profiles.find(p => p.id === id)?.name ?? '—';
  const fmt = n => n == null ? '—' : '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <table>
          <thead>
            <tr><th>Type</th><th>Owner</th><th>Balance</th><th>Return %</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {accounts.map(acct => editingId === acct.id ? (
              <tr key={acct.id}>
                <td><TypeBadge type={acct.account_type} /></td>
                <td>{ownerLabel(acct.owner_id)}</td>
                <td><input type="number" value={editForm.balance} onChange={e => setEditForm(f => ({ ...f, balance: e.target.value }))} style={{ width: 110 }} /></td>
                <td><input type="number" step="0.1" value={editForm.annual_return} onChange={e => setEditForm(f => ({ ...f, annual_return: e.target.value }))} style={{ width: 70 }} /></td>
                <td style={{ display: 'flex', gap: 6 }}>
                  <button onClick={() => handleSaveEdit(acct.id)} disabled={saving}>Save</button>
                  <button className="secondary" onClick={() => setEditingId(null)}>Cancel</button>
                </td>
              </tr>
            ) : (
              <tr key={acct.id}>
                <td><TypeBadge type={acct.account_type} /></td>
                <td>{ownerLabel(acct.owner_id)}</td>
                <td>{fmt(acct.balance)}</td>
                <td>{acct.annual_return}%</td>
                <td style={{ display: 'flex', gap: 6 }}>
                  <button className="secondary" onClick={() => { setEditingId(acct.id); setEditForm({ balance: acct.balance, annual_return: acct.annual_return, annual_contribution: acct.annual_contribution }); }}>Edit</button>
                  <button className="danger" onClick={() => handleDelete(acct.id)}>Delete</button>
                </td>
              </tr>
            ))}
            {showAddForm && (
              <tr>
                <td>
                  <select value={form.account_type} onChange={e => setForm(f => ({ ...f, account_type: e.target.value }))}>
                    {ACCOUNT_TYPES.map(t => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
                  </select>
                </td>
                <td>
                  <select value={form.owner_id} onChange={e => setForm(f => ({ ...f, owner_id: e.target.value }))}>
                    <option value="">— Owner —</option>
                    {profiles.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </td>
                <td><input type="number" placeholder="Balance" value={form.balance} onChange={e => setForm(f => ({ ...f, balance: e.target.value }))} style={{ width: 110 }} /></td>
                <td><input type="number" step="0.1" placeholder="7.0" value={form.annual_return} onChange={e => setForm(f => ({ ...f, annual_return: e.target.value }))} style={{ width: 70 }} /></td>
                <td style={{ display: 'flex', gap: 6 }}>
                  <button onClick={handleAdd} disabled={saving || !form.owner_id}>Add</button>
                  <button className="secondary" onClick={() => setShowAddForm(false)}>Cancel</button>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {!showAddForm && <button className="secondary" onClick={() => setShowAddForm(true)}>+ Add Account</button>}
    </div>
  );
}
