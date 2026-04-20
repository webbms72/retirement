import React, { useEffect, useState, useRef } from 'react';
import { getProfiles, updateProfile, getSocialSecurity, updateSocialSecurity } from '../api/client.js';
import AccountsTable from '../components/AccountsTable.jsx';
import NQDCSchedule from '../components/NQDCSchedule.jsx';

function calcAge(dob) {
  if (!dob) return null;
  const today = new Date();
  const birth = new Date(dob);
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
  return age;
}

function useDebounce(fn, delay) {
  const timer = useRef(null);
  return (...args) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => fn(...args), delay);
  };
}

function PersonCard({ person, ss, onPersonChange, onSsChange }) {
  const age = calcAge(person.dob);
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="section-title">{person.name}{age != null ? ` — Age ${age}` : ''}</div>
      <div className="field">
        <label>Date of Birth</label>
        <input type="date" value={person.dob || ''} onChange={(e) => onPersonChange(person.id, { dob: e.target.value })} />
      </div>
      <div className="field">
        <label>Life Expectancy: {person.life_expectancy_age}</label>
        <input type="range" min={70} max={100} value={person.life_expectancy_age || 88}
          onChange={(e) => onPersonChange(person.id, { life_expectancy_age: parseInt(e.target.value, 10) })} />
        <div style={{ display: 'flex', justifyContent: 'space-between', color: '#90a4ae', fontSize: 11 }}>
          <span>70</span><span>100</span>
        </div>
      </div>
      <div className="field">
        <label>Pre-Retirement Salary ($/yr)</label>
        <input type="number" min={0} step={1000} value={person.pre_retirement_income || ''}
          onChange={(e) => onPersonChange(person.id, { pre_retirement_income: parseFloat(e.target.value) || 0 })} />
      </div>
      <div className="field">
        <label>State</label>
        <input type="text" value={person.state || 'DE'} readOnly style={{ opacity: 0.5 }} />
      </div>
      {ss && (
        <>
          <div className="section-title" style={{ marginTop: 16 }}>Social Security</div>
          <div className="three-col">
            <div className="field">
              <label>Benefit at 62 ($/mo)</label>
              <input type="number" min={0} value={ss.benefit_at_62 || ''}
                onChange={(e) => onSsChange(person.id, { benefit_at_62: parseFloat(e.target.value) || 0 })} />
            </div>
            <div className="field">
              <label>Benefit at FRA ($/mo)</label>
              <input type="number" min={0} value={ss.benefit_at_fra || ''}
                onChange={(e) => onSsChange(person.id, { benefit_at_fra: parseFloat(e.target.value) || 0 })} />
            </div>
            <div className="field">
              <label>Benefit at 70 ($/mo)</label>
              <input type="number" min={0} value={ss.benefit_at_70 || ''}
                onChange={(e) => onSsChange(person.id, { benefit_at_70: parseFloat(e.target.value) || 0 })} />
            </div>
          </div>
          <div className="two-col">
            <div className="field">
              <label>Full Retirement Age</label>
              <input type="number" min={62} max={70} value={ss.fra_age || 67}
                onChange={(e) => onSsChange(person.id, { fra_age: parseInt(e.target.value, 10) })} />
            </div>
            <div className="field">
              <label>Survivor Benefit (%)</label>
              <input type="number" min={0} max={100} step={1}
                value={ss.survivor_benefit_pct != null ? ss.survivor_benefit_pct * 100 : ''}
                onChange={(e) => onSsChange(person.id, { survivor_benefit_pct: parseFloat(e.target.value) / 100 || 0 })} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function ProfileTab() {
  const [profiles, setProfiles] = useState([]);
  const [ssData, setSsData] = useState({});
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const profs = await getProfiles();
        setProfiles(profs);
        const ssMap = {};
        for (const p of profs) {
          try { ssMap[p.id] = await getSocialSecurity(p.id); }
          catch { ssMap[p.id] = null; }
        }
        setSsData(ssMap);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const debouncedUpdateProfile = useDebounce(async (id, fullProfile) => {
    try {
      const updated = await updateProfile(id, fullProfile);
      setProfiles(prev => prev.map(p => p.id === id ? { ...p, ...updated } : p));
    } catch (err) { console.error('Profile update failed:', err); }
  }, 500);

  const debouncedUpdateSs = useDebounce(async (profileId, patch) => {
    try {
      const current = ssData[profileId];
      const updated = await updateSocialSecurity(profileId, { ...current, ...patch });
      setSsData(prev => ({ ...prev, [profileId]: { ...prev[profileId], ...updated } }));
    } catch (err) { console.error('SS update failed:', err); }
  }, 500);

  if (loading) return <div style={{ color: '#90a4ae' }}>Loading profile…</div>;
  if (error) return <div style={{ color: '#ef5350' }}>Error: {error}</div>;

  return (
    <div>
      <div className="two-col">
        <div>
          <h2 style={{ color: '#4fc3f7', fontSize: 16, marginBottom: 16 }}>People</h2>
          {profiles.map(person => (
            <PersonCard key={person.id} person={person} ss={ssData[person.id]}
              onPersonChange={(id, patch) => {
                const current = profiles.find(p => p.id === id);
                if (!current) return;
                const merged = { ...current, ...patch };
                setProfiles(prev => prev.map(p => p.id === id ? merged : p));
                debouncedUpdateProfile(id, merged);
              }}
              onSsChange={(profileId, patch) => {
                setSsData(prev => ({ ...prev, [profileId]: { ...prev[profileId], ...patch } }));
                debouncedUpdateSs(profileId, patch);
              }}
            />
          ))}
        </div>
        <div>
          <h2 style={{ color: '#4fc3f7', fontSize: 16, marginBottom: 16 }}>Accounts</h2>
          <AccountsTable accounts={accounts} profiles={profiles} onAccountsChange={setAccounts} />
          <NQDCSchedule accounts={accounts} onAccountsChange={setAccounts} />
        </div>
      </div>
    </div>
  );
}
