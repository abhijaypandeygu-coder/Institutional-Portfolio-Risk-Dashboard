import React, { useEffect, useRef } from 'react';
import { LayoutDashboard, ShieldAlert, ChartNoAxesCombined, FlaskConical, Cable, Search, Command, ChevronDown, PanelLeft, ArrowUpRight } from 'lucide-react';
import { cn } from '../utils/cn';
export type DashboardView = 'overview' | 'alerts' | 'liquidity' | 'stress' | 'providers';
const views = [
  { id: 'overview', name: 'Overview', icon: LayoutDashboard },
  { id: 'alerts', name: 'Risk Alerts', icon: ShieldAlert },
  { id: 'liquidity', name: 'Liquidity', icon: ChartNoAxesCombined },
  { id: 'stress', name: 'Stress Testing', icon: FlaskConical },
  { id: 'providers', name: 'Data Feeds', icon: Cable },
] as const;
type Props = { view: DashboardView; onView: (v: DashboardView) => void; portfolio: string; onPortfolio: (id: string) => void; portfolios: { portfolio_id: string; portfolio_name: string }[]; onSearch: () => void; children: React.ReactNode };
export function AppShell({ view, onView, portfolio, onPortfolio, portfolios, onSearch, children }: Props) {
  const mobileNav = useRef<HTMLDetailsElement>(null);
  useEffect(() => { window.scrollTo(0, 0); }, [view]);
  const navigation = (close?: () => void) => <nav aria-label="Dashboard views" className="space-y-1">{views.map(v => <button type="button" key={v.id} aria-current={view === v.id ? 'page' : undefined} onClick={() => { onView(v.id); close?.(); }} className={cn('flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium', view === v.id ? 'bg-brand text-white' : 'text-secondary hover:bg-hover hover:text-ink')}><v.icon className="size-4 shrink-0" strokeWidth={1.7} />{v.name}</button>)}</nav>;
  return <div className="app-shell min-h-dvh bg-canvas text-ink">
    <a className="ui-skip-link rounded-lg bg-brand px-4 py-3 text-sm text-white" href="#main-content">Skip to content</a>
    <aside className="app-sidebar hidden lg:flex" aria-label="Workspace sidebar">
      <button type="button" onClick={() => onView('overview')} className="mb-12 flex items-center gap-2.5 rounded-xl px-2 text-left"><span className="flex size-9 items-center justify-center rounded-xl bg-ink text-white"><ChartNoAxesCombined className="size-5" strokeWidth={1.7} /></span><span className="text-xl font-semibold">FinSight</span></button>
      <p className="mb-3 px-3 text-xs font-medium text-muted">Workspace</p>{navigation()}
      <div className="mt-auto border-t border-line px-3 pt-5"><span className="flex items-center gap-2 text-xs font-medium text-secondary"><span className="size-1.5 rounded-full bg-muted" />Local workspace</span><p className="mt-2 text-xs leading-relaxed text-muted">Portfolio analytics<br />and risk intelligence.</p></div>
    </aside>
    <div className="app-workspace min-w-0">
      <header className="app-toolbar flex flex-wrap items-center justify-between gap-3 border-b border-line bg-canvas px-4 py-4 sm:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <details ref={mobileNav} className="relative lg:hidden"><summary aria-label="Open navigation" className="list-none rounded-lg border border-line bg-surface p-2.5"><PanelLeft className="size-4" /></summary><div className="absolute left-0 top-12 z-40 w-56 rounded-2xl border border-line bg-surface p-3 shadow-lg">{navigation(() => { mobileNav.current?.removeAttribute('open'); mobileNav.current?.querySelector<HTMLElement>('summary')?.focus(); })}</div></details>
          <div className="hidden items-center gap-2 text-sm sm:flex"><span className="text-muted">Workspace</span><span className="text-line-strong">/</span><span className="font-medium">{views.find(v => v.id === view)?.name}</span></div>
          <span className="text-base font-semibold sm:hidden">FinSight</span>
        </div>
        <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2 sm:gap-3">
          <label className="relative block min-w-0"><span className="sr-only">Select active portfolio</span><select value={portfolio} onChange={e => onPortfolio(e.target.value)} className="max-w-48 appearance-none rounded-lg border border-line bg-surface py-2.5 pl-3 pr-8 text-xs font-medium text-secondary sm:max-w-56">{portfolios.map(p => <option key={p.portfolio_id} value={p.portfolio_id}>{p.portfolio_name}</option>)}</select><ChevronDown aria-hidden className="pointer-events-none absolute right-2.5 top-3 size-3.5 text-muted" /></label>
          <button type="button" onClick={onSearch} aria-label="Open command palette" className="flex items-center gap-2 rounded-lg border border-line bg-surface p-2.5 text-muted sm:min-w-40"><Search className="size-4" /><span className="hidden text-xs sm:inline">Search anything</span><kbd className="ml-auto hidden items-center gap-0.5 text-xs sm:flex"><Command className="size-3" />K</kbd></button>
        </div>
      </header>
      <main id="main-content" tabIndex={-1} className="app-content mx-auto min-w-0 max-w-screen-2xl space-y-7 p-4 sm:p-8 lg:p-10">{children}</main>
      <footer className="px-4 pb-6 text-xs text-muted sm:px-8 lg:px-10">FinSight <span className="mx-2 text-line-strong">·</span> Portfolio workspace</footer>
    </div>
  </div>;
}
