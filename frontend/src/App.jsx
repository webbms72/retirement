import React, { useState } from 'react';
import ProfileTab from './tabs/ProfileTab.jsx';
import ScenariosTab from './tabs/ScenariosTab.jsx';
import ResultsTab from './tabs/ResultsTab.jsx';
import MonteCarloTab from './tabs/MonteCarloTab.jsx';

const TABS = [
  { id: 'profile', label: 'Profile' },
  { id: 'scenarios', label: 'Scenarios' },
  { id: 'results', label: 'Results' },
  { id: 'montecarlo', label: 'Monte Carlo' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('profile');

  return (
    <div style={{ minHeight: '100vh' }}>
      <header style={{
        background: '#0a1628',
        borderBottom: '1px solid #1e3a5f',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
      }}>
        <span style={{ color: '#4fc3f7', fontWeight: 700, fontSize: 18 }}>
          Retirement Calculator
        </span>
      </header>

      <nav className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={activeTab === tab.id ? 'active' : ''}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="tab-content">
        {activeTab === 'profile' && <ProfileTab />}
        {activeTab === 'scenarios' && <ScenariosTab />}
        {activeTab === 'results' && <ResultsTab />}
        {activeTab === 'montecarlo' && <MonteCarloTab />}
      </main>
    </div>
  );
}
