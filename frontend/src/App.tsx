import React, { useState } from 'react';
import { ExternalProvidersPage } from './modules/dashboard/ExternalProvidersPage';
import { PortfolioOverviewPage } from './modules/dashboard/portfolio-overview/PortfolioOverviewPage';
import { AlertsDashboardPage } from './modules/dashboard/alerts-dashboard/AlertsDashboardPage';
import { LiquidityDashboardPage } from './modules/dashboard/liquidity-dashboard/LiquidityDashboardPage';
import { StressTestingDashboardPage } from './modules/dashboard/stress-dashboard/StressTestingDashboardPage';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'alerts' | 'liquidity' | 'stress' | 'providers'>('overview');

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Institutional Top Navigation Header */}
      <header style={{
        backgroundColor: '#1e293b',
        borderBottom: '1px solid #334155',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            fontWeight: 'bold',
            fontSize: '18px',
            color: '#38bdf8',
            letterSpacing: '0.5px'
          }}>
            INSTITUTIONAL RISK DASHBOARD
          </div>
          <span style={{
            fontSize: '11px',
            backgroundColor: '#0369a1',
            padding: '2px 8px',
            borderRadius: '4px',
            textTransform: 'uppercase'
          }}>
            M15 Platform Live
          </span>
        </div>

        {/* Navigation Tabs */}
        <nav style={{ display: 'flex', gap: '8px' }}>
          {[
            { id: 'overview', label: 'Portfolio Overview' },
            { id: 'alerts', label: 'Risk Alerts' },
            { id: 'liquidity', label: 'Liquidity Analytics' },
            { id: 'stress', label: 'Stress Testing' },
            { id: 'providers', label: 'Data Providers' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              style={{
                backgroundColor: activeTab === tab.id ? '#0284c7' : '#0f172a',
                color: activeTab === tab.id ? '#ffffff' : '#94a3b8',
                border: '1px solid #334155',
                padding: '6px 14px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 500,
                transition: 'all 0.15s ease'
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Main Content Area */}
      <main style={{ flex: 1, padding: '24px', backgroundColor: '#0f172a' }}>
        {activeTab === 'overview' && <PortfolioOverviewPage portfolioId="PORTFOLIO_US_EQUITIES" />}
        {activeTab === 'alerts' && <AlertsDashboardPage />}
        {activeTab === 'liquidity' && <LiquidityDashboardPage />}
        {activeTab === 'stress' && <StressTestingDashboardPage />}
        {activeTab === 'providers' && <ExternalProvidersPage />}
      </main>
    </div>
  );
};
