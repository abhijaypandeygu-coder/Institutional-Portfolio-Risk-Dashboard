import React from 'react';
import { KpiCard } from '../KpiCard';
export type CanvasItem = { id: string; name: string; component: React.ComponentType; x: number; y: number; width: number; height: number };
function PortfolioValue() { return <KpiCard title="Portfolio value · synthetic" value={1250000} unit="INR" tooltip="Synthetic preview data; no account connection." />; }
export const canvasItems: CanvasItem[] = [
  { id: 'portfolio-value-reference', name: 'Portfolio value · reference', component: PortfolioValue, x: 64, y: 64, width: 320, height: 140 },
];
