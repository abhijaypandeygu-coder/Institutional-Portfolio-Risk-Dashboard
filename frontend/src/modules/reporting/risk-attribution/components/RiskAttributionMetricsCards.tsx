import React from 'react';
import {
  ShieldCheck,
  Cpu,
  Fingerprint,
  TrendingUp,
  CheckCircle2,
  AlertTriangle,
  Scale,
} from 'lucide-react';
import {
  RiskComposition,
  ReconciliationStatusType,
  RiskMeasureType,
} from '../../../../types/riskAttribution';

interface RiskAttributionMetricsCardsProps {
  authoritativeValue?: number;
  riskMeasure: RiskMeasureType;
  riskMeasureUnit: string;
  riskComposition: RiskComposition;
  reconciliationStatus: ReconciliationStatusType;
}

export const RiskAttributionMetricsCards: React.FC<RiskAttributionMetricsCardsProps> = ({
  authoritativeValue,
  riskMeasure,
  riskMeasureUnit,
  riskComposition,
  reconciliationStatus,
}) => {
  const getReconciliationBadge = (status: ReconciliationStatusType) => {
    switch (status) {
      case 'EXACT_RECONCILIATION':
        return {
          label: 'EXACT (Euler Reconciled)',
          bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
          icon: CheckCircle2,
        };
      case 'ROUNDING_DIFFERENCE':
        return {
          label: 'ROUNDING (Within Tol)',
          bg: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
          icon: Scale,
        };
      case 'RESIDUAL_PRESENT':
        return {
          label: 'RESIDUAL DETECTED',
          bg: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
          icon: AlertTriangle,
        };
      default:
        return {
          label: status,
          bg: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
          icon: AlertTriangle,
        };
    }
  };

  const recBadge = getReconciliationBadge(reconciliationStatus);
  const RecIcon = recBadge.icon;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 p-6 bg-slate-950">
      {/* 1. Authoritative Total Risk */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative overflow-hidden">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">
            Total {riskMeasure === 'PORTFOLIO_VOLATILITY' ? 'Volatility' : 'Risk'}
          </span>
          <ShieldCheck className="w-4 h-4 text-indigo-400" />
        </div>
        <div className="text-2xl font-bold text-slate-100">
          {authoritativeValue !== undefined
            ? `${(authoritativeValue * 100).toFixed(2)}%`
            : 'N/A'}
        </div>
        <div className="text-xs text-slate-400 mt-2 flex items-center justify-between">
          <span>{riskMeasureUnit}</span>
          <span className="text-indigo-400 font-mono text-[11px]">M07.09 Official</span>
        </div>
      </div>

      {/* 2. Systematic Risk */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative overflow-hidden">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">Systematic Risk</span>
          <Cpu className="w-4 h-4 text-cyan-400" />
        </div>
        <div className="text-2xl font-bold text-slate-100">
          {riskComposition.systematic_risk !== undefined
            ? `${(riskComposition.systematic_risk * 100).toFixed(2)}%`
            : 'N/A'}
        </div>
        <div className="text-xs text-slate-400 mt-2 flex items-center justify-between">
          <span>
            {riskComposition.systematic_percentage !== undefined
              ? `${riskComposition.systematic_percentage.toFixed(1)}% of total risk`
              : 'Multi-factor model'}
          </span>
          <span className="text-cyan-400 font-mono text-[11px]">M08.05</span>
        </div>
      </div>

      {/* 3. Idiosyncratic Residual Risk */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative overflow-hidden">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">Idiosyncratic Risk</span>
          <Fingerprint className="w-4 h-4 text-purple-400" />
        </div>
        <div className="text-2xl font-bold text-slate-100">
          {riskComposition.idiosyncratic_risk !== undefined
            ? `${(riskComposition.idiosyncratic_risk * 100).toFixed(2)}%`
            : 'N/A'}
        </div>
        <div className="text-xs text-slate-400 mt-2 flex items-center justify-between">
          <span>
            {riskComposition.idiosyncratic_percentage !== undefined
              ? `${riskComposition.idiosyncratic_percentage.toFixed(1)}% of total risk`
              : 'Residual variance'}
          </span>
          <span className="text-purple-400 font-mono text-[11px]">M08.06</span>
        </div>
      </div>

      {/* 4. Audit Reconciliation Status */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative overflow-hidden">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">Euler Reconciliation</span>
          <Scale className="w-4 h-4 text-slate-400" />
        </div>
        <div className="mt-1 flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold border ${recBadge.bg}`}
          >
            <RecIcon className="w-3.5 h-3.5" />
            {recBadge.label}
          </span>
        </div>
        <div className="text-xs text-slate-400 mt-2.5 flex items-center justify-between">
          <span>Tolerance: 1e-4</span>
          <span className="text-slate-400 font-mono text-[11px]">Sum(RC) = Total</span>
        </div>
      </div>
    </div>
  );
};
