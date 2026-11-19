import { ChartTimeAxis } from './ChartTimeAxis';
import { useLiveRefresh, LiveUpdateControls } from '../../hooks/useLiveRefresh';
import React, { useEffect, useMemo, useState } from 'react';
import { Download, RotateCcw, ZoomIn, ZoomOut } from 'lucide-react';
import { ModalSurface } from '../ModalSurface';
import { cn } from '../../utils/cn';
import { excessUnavailableReason, axisDomain, timestamp, aggregate, align, clean, drawdown, finite, indexed, monthly, recovery, relative, rolling, statistics } from '../../utils/performanceAnalytics';
import type { Frequency, Observation } from '../../utils/performanceAnalytics';
import type { PortfolioOverviewResponse } from '../../types/dashboard';
type Range = '1D'|'1W'|'1M'|'3M'|'6M'|'1Y'|'All';
type Event = { event_id:string; event_title:string; event_category:string; occurrence_time:string; event_description?:string; details?:unknown; source_module?:string };
type LatestQuote = {symbol:string;price:number;currency?:string;source_time?:string;retrieved_at:string;market_state?:string};
type Benchmark = {points:{timestamp:string;value:number}[];currency?:string;symbol:string;return_treatment?:string;status:string;retrieved_at?:string};
const pct=(n:number|null, signed=true)=>n===null||!Number.isFinite(n)?'Unavailable':`${signed&&n>0?'+':''}${(n*100).toFixed(2)}%`;
const formatDate=(t:number)=>new Date(t).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'});
const button='inline-flex items-center justify-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-2 text-xs font-medium text-secondary hover:bg-canvas';
const field='min-w-0 max-w-full rounded-lg border border-line bg-canvas px-3 py-2 text-xs text-secondary';
const horizons:Record<Range,number>={'1D':1,'1W':7,'1M':31,'3M':93,'6M':186,'1Y':366,All:3650};
async function read(url:string,signal:AbortSignal){const r=await fetch(url,{signal});if(!r.ok)throw new Error(`Request failed (HTTP ${r.status})`);return r.json();}
function MiniChart({title,lines,unit='%'}:{title:string;lines:{name:string;color:string;points:Observation[]}[];unit?:string}){
 const values=lines.flatMap(l=>l.points.map(p=>p.value));const times=lines.flatMap(l=>l.points.map(p=>p.time));
 const min=Math.min(0,...values),max=Math.max(0,...values),span=max-min||1,start=Math.min(...times),end=Math.max(...times);
 return <section className="min-w-0 rounded-xl border border-line bg-surface p-4"><h4 className="text-sm font-semibold text-ink">{title}</h4>{values.length>1?<><svg role="img" aria-label={`${title}. ${lines.map(l=>`${l.name}: ${l.points.length} observations`).join('. ')}. Values are available in the analytics table.`} viewBox="0 0 500 150" className="mt-3 h-36 w-full" preserveAspectRatio="none"><line x1="4" x2="496" y1={130-(0-min)/span*115} y2={130-(0-min)/span*115} stroke="#e5e5ea"/>{lines.map(l=><polyline key={l.name} fill="none" stroke={l.color} strokeWidth="1.7" vectorEffect="non-scaling-stroke" points={l.points.map(p=>`${4+(p.time-start)/(end-start||1)*492},${130-(p.value-min)/span*115}`).join(' ')}/>)}</svg><div className="flex flex-wrap gap-3 text-xs text-muted">{lines.map(l=><span key={l.name}>{l.name}: {l.points.length?`${l.points[l.points.length-1].value.toFixed(2)}${unit}`:'Unavailable'}</span>)}</div></>:<p className="flex h-36 items-center text-xs text-muted">Insufficient regular observations for this calculation.</p>}</section>;
}
export function PerformanceChart({headline,portfolioId,overview,range,onRange}:{headline?:{label:string;display:string;note:string};portfolioId:string;overview:PortfolioOverviewResponse|null;range:Range;onRange:(r:Range)=>void}){
 const [latestQuote,setLatestQuote]=useState<LatestQuote|null>(null);
 const [benchmarkId,setBenchmarkId]=useState('SPY'),[benchmarkChoice,setBenchmarkChoice]=useState('SPY'),[custom,setCustom]=useState('');
 const [frequency,setFrequency]=useState<Frequency>('DAILY'),[method,setMethod]=useState<'TWR'|'MWR'|'NAV'>('TWR');
 const [mode,setMode]=useState<'returns'|'nav'|'excess'|'drawdown'>('returns');
 const [showPortfolio,setShowPortfolio]=useState(true),[showBenchmark,setShowBenchmark]=useState(true);
 const [benchmark,setBenchmark]=useState<Benchmark|null>(null),[history,setHistory]=useState<Observation[]>([]),[events,setEvents]=useState<Event[]>([]),[report,setReport]=useState<any>(null);
 const [errors,setErrors]=useState<string[]>([]),[benchmarkError,setBenchmarkError]=useState('');
 const [viewNotice,setViewNotice]=useState('');
 const [activeLine,setActiveLine]=useState<string|null>(null);
 const [selected,setSelected]=useState<number|null>(null),[event,setEvent]=useState<Event|null>(null),[zoom,setZoom]=useState<[number,number]|null>(null),[drag,setDrag]=useState<number|null>(null);
 const [analyticsSource,setAnalyticsSource]=useState<'portfolio'|'benchmark'>('benchmark'),[rf,setRf]=useState(0);
 const currency=overview?.portfolio.base_currency||'USD';
 const money=(v:number|undefined|null)=>v===undefined||v===null?'Unavailable':new Intl.NumberFormat('en-US',{style:'currency',currency,maximumFractionDigits:2}).format(v);
 useEffect(()=>{setZoom(null);setSelected(null);},[portfolioId,range,frequency,method,benchmarkId]);
 useEffect(()=>{setHistory([]);setEvents([]);setReport(null);setErrors([]);},[portfolioId,range,method,currency]);
 const portfolioRefresh=useLiveRefresh(`performance:${portfolioId}:${range}:${method}:${currency}`,async signal=>{
  if(!portfolioId)return;const controller={signal};
  const end=new Date(),start=new Date(end.getTime()-horizons[range]*86400000);
  const query=`portfolio_id=${encodeURIComponent(portfolioId)}&start_time=${encodeURIComponent(start.toISOString())}&end_time=${encodeURIComponent(end.toISOString())}`;
  const failures:string[]=[];
  async function load(){
   const results=await Promise.allSettled([
    read(`/api/v1/dashboard/history/portfolio-values?${query}&frequency=DAILY&downsample_limit=10000`,controller.signal),
    read(`/api/v1/dashboard/history/events?${query}&page_size=200`,controller.signal),
    read(`/api/v1/reports/performance/archive/${encodeURIComponent(portfolioId)}?limit=20`,controller.signal),
   ]);
   if(controller.signal.aborted)return;
   if(results[0].status==='fulfilled')setHistory(clean((results[0].value.observations||[]).filter((p:any)=>!['INVALID','UNAVAILABLE'].includes(p.quality_status)).flatMap((p:any)=>{const v=finite(p.value);return v===null?[]:[{time:timestamp(p.effective_at),value:v,nav:v}];})));else failures.push('Recorded NAV history could not be loaded.');
   if(results[1].status==='fulfilled'){setEvents(results[1].value.events||[]);if(results[1].value.total_count>200)failures.push('Only the first 200 recorded events are shown; narrow the period to see more.');}else failures.push('Portfolio event records could not be loaded.');
   if(results[2].status==='fulfilled'&&method!=='NAV'){
    let found=false;
    for(const run of results[2].value.slice(0,20).filter((r:any)=>timestamp(r.reporting_end_date)>=start.getTime())){
     try{const rep=await read(`/api/v1/reports/performance/runs/${encodeURIComponent(run.id)}`,controller.signal);
      const recordedMethods=[...new Set((rep.return_observations||[]).map((r:any)=>String(r.methodology).toUpperCase()))];
      const matches=recordedMethods.length===1?recordedMethods[0]===method:recordedMethods.length===0&&String(rep.methodology?.return_methodology).toUpperCase().startsWith(method);
      if(matches&&rep.portfolio?.reporting_currency===currency&&['COMPLETE','VALID'].includes(rep.performance_summary?.performance_data_status)&& (method!=='MWR'||timestamp(rep.reporting_period?.start_date)>=start.getTime())){setReport(rep);found=true;break;}
     }catch(e){if(controller.signal.aborted)return;}
    }
    if(!found&&!signal.aborted)setReport(null);
   }else if(results[2].status==='rejected')failures.push('Archived performance reports could not be loaded.');
   if(!controller.signal.aborted){setErrors(failures);}
  }
  await load();if(failures.length)throw new Error(failures.join(' '));
 });
 useEffect(()=>{setBenchmark(null);setBenchmarkError('');},[benchmarkId,range]);
 const benchmarkRefresh=useLiveRefresh(`benchmark:${benchmarkId}:${range}`,async signal=>{
  try{const d=await read(`/api/v1/dashboard/liquidity/benchmark-history?symbol=${encodeURIComponent(benchmarkId)}&range=${range}`,signal);if(d.status!=='available')throw new Error('Benchmark history unavailable. Previous observations are retained.');if(!signal.aborted){setBenchmark(d);setBenchmarkError('');}}
  catch(e){if(!signal.aborted)setBenchmarkError('Benchmark refresh failed. Previous observations are retained; their source time has not changed.');throw e;}
 });
 useEffect(()=>setLatestQuote(null),[benchmarkId]);
 const quoteRefresh=useLiveRefresh(`latest-quote:${benchmarkId}`,async signal=>{
  const quote=await read(`/api/v1/dashboard/liquidity/market-quote?symbol=${encodeURIComponent(benchmarkId)}`,signal);
  if(quote.symbol!==benchmarkId||quote.status!=='available'||typeof quote.price!=='number'||!Number.isFinite(quote.price)||quote.price<=0)throw new Error('Latest quote unavailable.');
  if(!signal.aborted)setLatestQuote(quote);
 });
 const busy=portfolioRefresh.running,benchmarkBusy=benchmarkRefresh.running;
 const rawPortfolio=useMemo(()=>{
  const cutoff=Date.now()-horizons[range]*86400000;
  const fallback=(overview?.nav_trend||[]).flatMap(p=>{const v=finite(p.nav);return v===null?[]:[{time:timestamp(p.timestamp),value:v,nav:v}];});
  return aggregate(clean(history.length?history:fallback).filter(p=>p.time>=cutoff),frequency);
 },[history,overview,frequency,range]);
 const portfolioSeries=useMemo(()=>{
  if(method==='NAV')return rawPortfolio;
  if(method==='MWR'||!report)return [];
  const rows=(report.return_observations||[]).filter((r:any)=>r.observation_status==='COMPLETE'&&finite(r.periodic_return)!==null&&finite(r.cumulative_return)!==null);
  if(!rows.length)return [];
  const start=rows[0];const values=[{time:timestamp(start.observation_start),value:100,nav:Number(start.beginning_value)},...rows.map((r:any)=>({time:timestamp(r.observation_end),value:100*(1+Number(r.cumulative_return)),nav:Number(r.ending_value)}))];
  const cutoff=Date.now()-horizons[range]*86400000;
  return aggregate(clean(values).filter(p=>p.time>=cutoff),frequency);
 },[report,method,rawPortfolio,frequency,range]);
 const benchmarkSeries=useMemo(()=>{const rows=clean((benchmark?.points||[]).map(p=>({time:timestamp(p.timestamp),value:p.value})));return range==='1D'?rows:aggregate(rows,frequency);},[benchmark,frequency,range]);
 const sameCurrency=!!benchmark?.currency&&benchmark.currency===currency;
 const pStats=statistics(portfolioSeries,frequency,rf),bStats=statistics(benchmarkSeries,frequency,rf);
 const comparison=relative(sameCurrency?portfolioSeries:[],benchmarkSeries,frequency);
 const matched=comparison.aligned.a.length>1;
 const excessReason=excessUnavailableReason(method,portfolioSeries.length,benchmarkSeries.length,sameCurrency,comparison.aligned.a.length);
 useEffect(()=>{
  if(mode==='excess'&&excessReason&&!busy&&!benchmarkBusy){setMode('returns');setSelected(null);setZoom(null);setShowBenchmark(true);setViewNotice(`Switched to cumulative return. Excess return is unavailable: ${excessReason}`);}
 },[mode,excessReason,busy,benchmarkBusy]);
 const navBase=rawPortfolio[0]?.value;
 const pBase=matched?comparison.aligned.a:portfolioSeries,bBase=mode==='nav'?benchmarkSeries:matched?comparison.aligned.b:benchmarkSeries;
 const pIndex=indexed(pBase),bIndex=indexed(bBase);
 const within=(p:Observation)=>!zoom||(p.time>=zoom[0]&&p.time<=zoom[1]);
 const mwr=method==='MWR'&&report?finite(report.performance_summary?.period_return):null;
 const metrics:[string,number|null,string][]=[
  [method==='NAV'?'Unadjusted NAV change':'Portfolio return',method==='MWR'?mwr:pStats.total,method==='NAV'?'Unadjusted NAV change; cash flows are not neutralized.':method==='MWR'?'Archived money-weighted period return.':'From archived cash-flow-adjusted TWR observations.'],
  ['Benchmark return',bStats.total,'Adjusted-close proxy or price-index return; not the selected portfolio return.'],
  ['Excess return',matched?comparison.total:null,'Portfolio return minus benchmark return over identical observed dates, same currency.'],
  [method==='NAV'?'Annualized NAV change':'Annualized return',method==='MWR'&&report&&(timestamp(report.reporting_period.end_date)-timestamp(report.reporting_period.start_date))/86400000>=365?finite(report.performance_summary?.annualized_return):method==='MWR'?null:pStats.annualized,'Requires at least 365 elapsed days of portfolio observations.'],
  ['Annualized volatility',pStats.volatility,'Sample standard deviation, at least 20 regular period returns.'],
  [method==='NAV'?'Maximum NAV drawdown':'Maximum drawdown',pStats.drawdown,'Peak-to-trough decline in the selected portfolio series.'],
 ];
 const displayP=mode==='nav'?rawPortfolio:mode==='drawdown'?drawdown(pBase):mode==='excess'?comparison.excess:pIndex.map(p=>({...p,value:p.value-100}));
 const displayB=mode==='nav'?indexed(benchmarkSeries):mode==='drawdown'?drawdown(bBase):mode==='excess'?[]:bIndex.map(p=>({...p,value:p.value-100}));
 const lines=[...((mode==='excess'||showPortfolio)?[{name:mode==='excess'?'Excess return':mode==='nav'?'Recorded portfolio NAV':method==='NAV'?'Unadjusted NAV':'Portfolio',color:'#18743b',points:displayP.filter(within)}]:[]),...(showBenchmark&&mode!=='excess'?[{name:benchmarkId,color:'#0066cc',points:displayB.filter(within)}]:[])];
 const all=lines.flatMap(l=>l.points),times=[...new Set(all.map(p=>p.time))].sort((a,b)=>a-b),start=times[0],end=times[times.length-1];
 const primaryValues=mode==='nav'?displayP.filter(within).map(p=>p.value):all.map(p=>p.value);
 const {min,max,span}=axisDomain(primaryValues);
 const benchmarkAxis=axisDomain(displayB.filter(within).map(p=>p.value));
 const benchmarkY=(v:number)=>252-(v-benchmarkAxis.min)/benchmarkAxis.span*205;
 const lineY=(line:{name:string},v:number)=>mode==='nav'&&line.name===benchmarkId?benchmarkY(v):y(v);
 const x=(t:number)=>52+(t-start)/(end-start||1)*720,y=(v:number)=>252-(v-min)/span*205;
 const selectedTime=selected===null?times[times.length-1]:times[Math.min(selected,times.length-1)];
 const exact=(rows:Observation[],time:number)=>rows.find(p=>p.time===time);
 const selectedPoints=lines.flatMap(line=>{const point=exact(line.points,selectedTime);return point?[{line,point}]:[];});
 const focusedPoint=selectedPoints.find(item=>item.line.name===activeLine)||selectedPoints[0];
 const pointValue=focusedPoint?(mode==='nav'&&focusedPoint.line.name!==benchmarkId?money(focusedPoint.point.value):mode==='nav'?`${focusedPoint.point.value.toFixed(2)} index`:`${focusedPoint.point.value>0?'+':''}${focusedPoint.point.value.toFixed(2)}%`):'';
 const selectedBenchmarkPrice=benchmark?.points.find(p=>timestamp(p.timestamp)===selectedTime)?.value;
 const stockPrice=(value:number|undefined,unit?:string)=>value===undefined?'Unavailable':benchmarkId.startsWith('^')?`${new Intl.NumberFormat('en-US',{maximumFractionDigits:2}).format(value)} points`:unit&&/^[A-Z]{3}$/.test(unit)?new Intl.NumberFormat('en-US',{style:'currency',currency:unit,maximumFractionDigits:2}).format(value):unit?`${value.toLocaleString('en-US',{maximumFractionDigits:2})} ${unit}`:`${value.toFixed(2)} (currency unavailable)`;

 const pp=exact(pBase,selectedTime),bp=exact(bBase,selectedTime),pi=pp?pBase.findIndex(p=>p.time===pp.time):-1,bi=bp?bBase.findIndex(p=>p.time===bp.time):-1;
 const hoverP=pp&&pBase[0]?pp.value/pBase[0].value-1:null,hoverB=bp&&bBase[0]?bp.value/bBase[0].value-1:null;
 const hoverNav=exact(rawPortfolio,selectedTime)?.value??pp?.nav;
 const source=analyticsSource==='portfolio'?portfolioSeries:benchmarkSeries;
 const draw=drawdown(source),vols=[30,60,90].map(w=>({name:`${w} observations`,color:w===30?'#0066cc':w===60?'#9a6700':'#6941a5',points:rolling(source,w,frequency,'volatility',rf)}));
 const sharpe=rolling(source,63,frequency,'sharpe',rf),months=monthly(source),recover=recovery(source);
 const flowEvents:Event[]=(report?.return_observations||[]).flatMap((r:any)=>[['external_contributions','Contributions'],['external_withdrawals','Withdrawals']].flatMap(([key,label])=>Number(r[key])>0?[{event_id:`${r.id}-${key}`,event_title:`${label}: ${money(Number(r[key]))}`,event_category:'CASH_MOVEMENT',occurrence_time:r.observation_end,event_description:'External cash flow total for this archived observation period. Marker is at the observation end, not an inferred intraday flow time.',details:{observation_start:r.observation_start,observation_end:r.observation_end,amount:Number(r[key]),currency}}]:[]));
 const moveEvents:Event[]=portfolioSeries.slice(1).flatMap((p,i)=>{const previous=portfolioSeries[i];if(previous.value<=0)return [];const r=p.value/previous.value-1;return Math.abs(r)>=.05?[{event_id:`move-${p.time}`,event_title:`${method==='NAV'?'NAV change':'Portfolio period return'} ${pct(r)}`,event_category:'PERFORMANCE_MOVE',occurrence_time:new Date(p.time).toISOString(),event_description:'Calculated marker for an observed period move of at least 5% in absolute value. This is not an inferred trade or external market event.',details:{previous_observation:new Date(previous.time).toISOString(),methodology:method,period_return:r}}]:[];});
 const visibleEvents=[...events,...flowEvents,...moveEvents].filter(e=>{const t=timestamp(e.occurrence_time),floor=zoom?start:Math.floor(start/86400000)*86400000,ceil=zoom?end:Math.floor(end/86400000)*86400000+86399999;return Number.isFinite(t)&&times.length>1&&t>=floor&&t<=ceil;});
 function setZoomBy(factor:number){if(times.length<3)return;const full=[...portfolioSeries,...benchmarkSeries].map(p=>p.time);const floor=Math.min(...full),ceil=Math.max(...full),mid=(start+end)/2,half=(end-start)/2*factor;setZoom([Math.max(floor,mid-half),Math.min(ceil,mid+half)]);setSelected(null);}
 function exportData(){
  const header=['timestamp_utc','methodology','benchmark','portfolio_currency','portfolio_nav','portfolio_return','benchmark_return','excess_return','portfolio_drawdown'];
  const dates=[...new Set([...pBase,...bBase,...rawPortfolio].filter(within).map(p=>p.time))].sort((a,b)=>a-b);
  const quote=(v:unknown)=>{let s=String(v??'');if(typeof v==='string'&&/^[=+\-@]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
  const rows=dates.map(t=>{const p=exact(pBase,t),b=exact(bBase,t);const pr=p&&pBase[0]?p.value/pBase[0].value-1:null,br=b&&bBase[0]?b.value/bBase[0].value-1:null;return [new Date(t).toISOString(),method,benchmarkId,currency,exact(rawPortfolio,t)?.value??p?.nav,pr,br,matched&&pr!==null&&br!==null?pr-br:null,exact(drawdown(pBase),t)?.value];});
  const url=URL.createObjectURL(new Blob([[header,...rows].map(r=>r.map(quote).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`portfolio-performance-${portfolioId.replace(/[^a-z0-9_-]/gi,'_')}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 return <section aria-labelledby="performance-heading" className="min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-6 xl:col-span-9">
  <div className="flex flex-wrap items-start justify-between gap-4"><div><h2 id="performance-heading" className="text-lg font-semibold text-ink">Performance summary</h2><p className="mt-1 text-xs text-muted">Portfolio performance and benchmark comparison</p></div><div className="flex max-w-full flex-wrap gap-1 rounded-lg bg-canvas p-1" aria-label="Performance period">{(['1D','1W','1M','3M','6M','1Y','All'] as Range[]).map(r=><button key={r} type="button" aria-pressed={range===r} className={cn('rounded px-2.5 py-1.5 text-xs',range===r?'bg-surface font-semibold text-brand':'text-muted')} onClick={()=>onRange(r)}>{r}</button>)}</div></div>
  <div className="mt-4"><LiveUpdateControls /></div>
  <p role="status" className="mt-2 text-xs text-muted">{benchmarkRefresh.running?'Checking market history…':benchmarkRefresh.lastChecked?`Market history checked ${new Date(benchmarkRefresh.lastChecked).toLocaleTimeString()}`:'Waiting for the first market-data check.'} {benchmarkRefresh.error?`${benchmarkRefresh.error} Showing the last available data.`:''} Source retrieved: {benchmark?.retrieved_at?new Date(benchmark.retrieved_at).toLocaleString():'unavailable'}. Latest provider bar: {benchmark?.points?.length?new Date(benchmark.points[benchmark.points.length-1].timestamp).toLocaleString():'unavailable'}. Market-close periods can remain unchanged. Recorded NAV changes only when a new valuation is saved.</p>
  <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs text-muted">{headline?.label || 'Recorded portfolio NAV'} · {currency}</p><p className="mt-1 text-3xl font-semibold tabular-nums text-ink">{headline?.display || overview?.total_nav?.value_display||'Unavailable'}</p>{headline && <p className="mt-2 max-w-xl text-xs text-muted">{headline.note}</p>}</div><button type="button" className={button} onClick={exportData} disabled={!times.length}><Download className="size-3.5"/>Export chart CSV</button></div>
  <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-5 border-y border-line py-5 sm:grid-cols-3">{metrics.map(([label,value,help])=><div key={label}><dt className="text-xs text-muted" title={help}>{label}</dt><dd className={cn('mt-1 text-base font-semibold tabular-nums',value===null?'text-muted':value<0?'text-negative':label.includes('volatility')?'text-ink':'text-positive')}>{pct(value)}</dd></div>)}</dl>
  <div className="mt-4 flex flex-wrap items-end gap-3">
   <label className="text-xs text-muted">Benchmark<select aria-label="Performance benchmark" className={cn(field,'mt-1 block')} value={benchmarkChoice} onChange={e=>{setBenchmarkChoice(e.target.value);if(e.target.value==='custom'){setCustom('');}else setBenchmarkId(e.target.value);}}><option value="SPY">SPY · ETF adjusted close</option><option value="^GSPC">S&amp;P 500 · price index</option><option value="^NSEI">NIFTY 50 · price index</option><option value="custom">Custom ticker</option></select></label>
   <form onSubmit={e=>{e.preventDefault();if(/^[A-Za-z0-9^][A-Za-z0-9.\-^=]{0,23}$/.test(custom.trim())){setBenchmarkId(custom.trim().toUpperCase());setBenchmarkChoice('custom');}}} className="flex max-w-full gap-1"><input required pattern="[A-Za-z0-9^][A-Za-z0-9.\-^=]{0,23}" title="Enter a Yahoo Finance ticker, such as SPY or ^NSEI" aria-label="Custom benchmark ticker" placeholder="Custom ticker" maxLength={24} value={custom} onChange={e=>setCustom(e.target.value)} className={cn(field,'w-28')}/><button type="submit" className={button}>Apply</button></form>
   <label className="text-xs text-muted">Frequency<select aria-label="Performance frequency" className={cn(field,'mt-1 block')} value={frequency} onChange={e=>setFrequency(e.target.value as Frequency)}><option value="DAILY">Daily</option><option value="WEEKLY">Weekly</option><option value="MONTHLY">Monthly</option></select></label>
   <label className="text-xs text-muted">Methodology<select aria-label="Performance methodology" className={cn(field,'mt-1 block')} value={method} onChange={e=>setMethod(e.target.value as typeof method)}><option value="TWR">TWR · archived returns</option><option value="MWR">MWR · archived return</option><option value="NAV">Unadjusted NAV change</option></select></label>
  </div>
  <p className="mt-3 text-xs leading-relaxed text-muted">{busy?'Loading portfolio performance records…':method==='NAV'?'NAV change includes external flows. It is not a cash-flow-adjusted investment return.':!report?`No matching ${method} report is available for this portfolio. Its return and risk statistics cannot be inferred from the benchmark.`:method==='MWR'?'MWR is a period summary from an archived report; an IRR is not a daily return path.':'Portfolio line uses archived, cash-flow-adjusted TWR observations.'}</p>
  {(report?.caveats||[]).map((c:any,i:number)=><p key={i} className="mt-2 text-xs text-warning">Report caveat: {c.explanation}</p>)}{errors.map(e=><p role="alert" key={e} className="mt-2 text-xs text-warning">{e}</p>)}{benchmarkError&&<p role="alert" className="mt-2 text-xs text-warning">{benchmarkError}</p>}
  <div className="mt-4 flex flex-wrap items-center gap-3">{mode==='excess'?<span className="text-xs font-medium text-positive">Portfolio minus {benchmarkId}</span>:<><label className="flex items-center gap-1.5 text-xs text-positive"><input type="checkbox" checked={showPortfolio} onChange={e=>setShowPortfolio(e.target.checked)}/>Portfolio {mode==='nav'||method==='NAV'?'NAV':'performance'}</label><label className="flex items-center gap-1.5 text-xs text-brand"><input type="checkbox" checked={showBenchmark} onChange={e=>setShowBenchmark(e.target.checked)}/>{benchmarkId}</label></>}<label className="ml-auto text-xs text-muted">View <select aria-label="Chart view" className={field} value={mode} onChange={e=>{setMode(e.target.value as typeof mode);setSelected(null);setViewNotice('');setZoom(null);}}><option value="returns">Cumulative return</option><option value="nav">NAV / indexed benchmark</option><option value="excess" disabled={!!excessReason||busy||benchmarkBusy}>Excess return{excessReason?' · unavailable':''}</option><option value="drawdown">Drawdown</option></select></label></div>
  {viewNotice&&<p role="status" className="mt-3 rounded-lg bg-brand-soft p-3 text-xs text-secondary">{viewNotice}</p>}
  {(mode==='nav'||matched||(benchmark?.currency&&!sameCurrency))&&<p className="mt-2 text-xs text-muted">{mode==='nav'?'Left axis: recorded portfolio NAV. Right axis: benchmark index, starting at 100 over its own available history. These are independent scales, not matched investment returns.':matched?'Both series use the same observed calendar dates and start at 0% return.':''} {benchmark?.currency&& !sameCurrency?`Benchmark is ${benchmark.currency}; comparison to ${currency} requires FX conversion.`:''} </p>}
  {mode==='nav'&&rawPortfolio.length<2&&<p role="status" className="mt-3 rounded-lg bg-brand-soft p-3 text-xs text-secondary">{rawPortfolio.length===1?'Only one NAV snapshot is recorded. The green point is that valuation; a portfolio trend needs at least two snapshots. The benchmark can still be explored independently.':'No portfolio NAV snapshots are available for this period. The benchmark is shown independently.'}</p>}
  <div className="mt-3 flex flex-wrap gap-2"><button type="button" aria-label="Zoom in chart" className={button} onClick={()=>setZoomBy(.6)} disabled={times.length<3}><ZoomIn className="size-3.5"/>Zoom in</button><button type="button" aria-label="Zoom out chart" className={button} onClick={()=>setZoomBy(1.7)} disabled={!zoom}><ZoomOut className="size-3.5"/>Zoom out</button><button type="button" className={button} onClick={()=>{setZoom(null);setSelected(null);}} disabled={!zoom}><RotateCcw className="size-3.5"/>Reset zoom</button></div>
  {mode==='nav'&&<div className="mt-3 flex justify-between gap-3 text-xs"><span className="text-positive">Portfolio NAV · {currency}</span><span className="text-brand">{benchmarkId} index · start 100</span></div>}
  {all.length?<><div className="relative mt-3 h-64 sm:h-80"><svg role="img" aria-label={`${mode} chart. ${lines.map(l=>`${l.name}: ${l.points.length} observations`).join('. ')}. Use the observation slider or recorded data table for exact values. Drag horizontally to zoom.`} viewBox="0 0 860 300" preserveAspectRatio="none" className="h-full w-full touch-pan-y" onPointerDown={e=>{if(e.pointerType==='touch')return;setDrag(e.clientX);e.currentTarget.setPointerCapture(e.pointerId);}} onPointerMove={e=>{const box=e.currentTarget.getBoundingClientRect();let closest:{time:number;name:string;distance:number}|null=null;for(const line of lines){for(const point of line.points){const dx=x(point.time)/860*box.width-(e.clientX-box.left),dy=lineY(line,point.value)/300*box.height-(e.clientY-box.top);const distance=dx*dx+dy*dy;if(!closest||distance<closest.distance)closest={time:point.time,name:line.name,distance};}}if(closest){setSelected(times.indexOf(closest.time));setActiveLine(closest.name);}}} onPointerUp={e=>{if(drag!==null&&Math.abs(e.clientX-drag)>15&&times.length>2){const box=e.currentTarget.getBoundingClientRect();const time=(client:number)=>start+Math.max(0,Math.min(1,((client-box.left)/box.width*860-52)/720))*(end-start);setZoom([Math.min(time(drag),time(e.clientX)),Math.max(time(drag),time(e.clientX))]);setSelected(null);}setDrag(null);if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);}} onPointerCancel={()=>setDrag(null)}>
    {[0,1,2,3].map(i=><g key={i}><line x1="52" x2="772" y1={47+i*205/3} y2={47+i*205/3} stroke="#e5e5ea"/><text x="44" y={51+i*205/3} textAnchor="end" fill="#6e6e73" fontSize="11">{mode==='nav'?new Intl.NumberFormat('en',{notation:'compact'}).format(max-i*span/3):`${(max-i*span/3).toFixed(1)}%`}</text></g>)}
    {mode==='nav'&&showBenchmark&&displayB.length>0&&[0,1,2,3].map(i=><text key={`benchmark-axis-${i}`} x="784" y={51+i*205/3} fill="#0066cc" fontSize="11">{(benchmarkAxis.max-i*benchmarkAxis.span/3).toFixed(1)}</text>)}
    {lines.map(l=><g key={l.name}><polyline fill="none" stroke={l.color} strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" points={l.points.map(p=>`${x(p.time)},${lineY(l,p.value)}`).join(' ')}/>{l.points.length===1&&<circle cx={x(l.points[0].time)} cy={lineY(l,l.points[0].value)} r="4" fill={l.color}/>}</g>)}
    {selectedTime!==undefined&&<g><line x1={x(selectedTime)} x2={x(selectedTime)} y1="32" y2="264" stroke="#8e8e93" strokeDasharray="4 4"/>{lines.flatMap(l=>{const p=exact(l.points,selectedTime);return p?[<circle key={l.name} cx={x(p.time)} cy={lineY(l,p.value)} r="4" fill={l.color}/>]:[];})}</g>}
    {visibleEvents.map((e,i)=><g key={e.event_id}><title>{e.event_title}</title><circle cx={x(Math.max(start,Math.min(end,timestamp(e.occurrence_time))))} cy={278-(i%2)*10} r="4" fill="#8a5100"/></g>)}
   </svg>
   {focusedPoint&&<div role="tooltip" aria-label="Selected graph point" className="pointer-events-none absolute z-10 w-44 rounded-xl border border-line bg-surface px-3 py-2 shadow-md" style={{width:'min(11rem, calc(100% - 16px))',left:`clamp(8px, calc(${x(focusedPoint.point.time)/860*100}% ${x(focusedPoint.point.time)>430?'- min(11rem, calc(100% - 16px)) - 12px':'+ 12px'}), calc(100% - min(11rem, calc(100% - 16px)) - 8px))`,top:`clamp(110px, ${lineY(focusedPoint.line,focusedPoint.point.value)/300*100}%, calc(100% - 110px))`,transform:'translateY(-50%)'}}>
    <p className="text-xs text-muted">{formatDate(focusedPoint.point.time)}{range==='1D'?` · ${new Date(focusedPoint.point.time).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'UTC'})} UTC`:''}</p>
    <p className="mt-1 break-words text-xs font-medium text-secondary">{focusedPoint.line.name}</p><p className="mt-0.5 text-base font-semibold tabular-nums text-ink">{pointValue}</p>
    {focusedPoint.line.name===benchmarkId?<div className="mt-2 border-t border-line pt-2">
     <p className="text-xs text-muted">{benchmarkId.startsWith('^')?'Index at selected point':'Adjusted price at point'}: <span className="font-medium tabular-nums text-secondary">{stockPrice(selectedBenchmarkPrice,benchmark?.currency)}</span></p>
     <p className="mt-2 text-xs text-muted">{benchmarkId.startsWith('^')?'Latest index level':'Latest stock / ETF price'}</p>
     <p className="text-base font-semibold tabular-nums text-ink">{stockPrice(latestQuote?.price,latestQuote?.currency)}</p>
     <p className="mt-1 text-xs text-muted">{quoteRefresh.error?'Refresh failed · previous quote':latestQuote?.source_time?`As of ${new Date(latestQuote.source_time).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})}`:latestQuote?'Source time unavailable':quoteRefresh.running?'Checking quote…':'Quote unavailable'} · may be delayed</p>
    </div>:<div className="mt-2 border-t border-line pt-2"><p className="text-xs text-muted">Latest recorded portfolio NAV</p><p className="text-sm font-semibold tabular-nums text-ink">{overview?.total_nav?.value_display||'Unavailable'}</p></div>}

   </div>}
   </div><ChartTimeAxis start={start} end={end} observations={times.length} /><label className="mt-3 block text-xs text-muted">Explore chart observation<input type="range" min="0" max={Math.max(0,times.length-1)} disabled={times.length<2} value={selected??times.length-1} onChange={e=>{setSelected(Number(e.target.value));setActiveLine(null);}} className="mt-1 w-full accent-brand"/></label>
   <div className="mt-3 rounded-xl border border-line bg-canvas p-4"><p className="text-xs font-semibold text-secondary">{new Date(selectedTime).toISOString()} · UTC</p><dl className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">{[
    ['Portfolio NAV',money(hoverNav)],['Benchmark indexed value',bp&&bBase[0]?(bp.value/bBase[0].value*100).toFixed(2):'Unavailable'],[frequency==='DAILY'&&range!=='1D'?'Daily portfolio return':'Observed portfolio return',pp&&pi>0&&pBase[pi-1].value>0&&(frequency!=='DAILY'||pp.time-pBase[pi-1].time<=4*86400000)?pct(pp.value/pBase[pi-1].value-1):'Unavailable'],[method==='NAV'?'Cumulative NAV change':'Cumulative portfolio return',pct(hoverP)],['Benchmark return',pct(hoverB)],['Excess return',matched&&hoverP!==null&&hoverB!==null?pct(hoverP-hoverB):'Unavailable'],
   ].map(([label,value])=><div key={label}><dt className="text-muted">{label}</dt><dd className="mt-1 font-medium tabular-nums text-ink">{value}</dd></div>)}</dl></div>
  </>:<p role="status" className="flex min-h-52 items-center justify-center text-sm text-muted">{busy||benchmarkBusy?'Loading chart observations…':'No observations for this view. Select cumulative return or enable a series.'}</p>}
  <p className="mt-3 text-xs leading-relaxed text-muted">Benchmark: {benchmarkId} · {benchmark?.return_treatment==='price_index'?'Price index; dividends excluded.':'Provider-adjusted close proxy; corporate actions use provider adjustments.'} Normalization uses the first available observation, not the final NAV. {range==='1D'?'Intraday observations are not annualized.':'Periods under one year are not annualized.'} Dates are aligned in UTC; no missing values are filled. Zoom changes the plotted window; summary metrics retain the full selected period.</p>
  <details className="mt-5 border-t border-line pt-4"><summary className="text-sm font-medium text-secondary">Events &amp; cash flows ({visibleEvents.length})</summary><p className="mt-2 text-xs text-muted">Recorded deposits, withdrawals, trades, alerts, breaches and market events appear when supplied by the portfolio event ledger. Observed period moves of at least 5% are marked separately. No external market news is invented.</p><div className="mt-3 flex flex-wrap gap-2">{visibleEvents.map(e=><button type="button" key={e.event_id} className={button} onClick={()=>setEvent(e)}>{formatDate(timestamp(e.occurrence_time))} · {e.event_title}</button>)}</div>{!visibleEvents.length&&<p className="mt-3 text-xs text-muted">No recorded events in the visible chart window.</p>}</details>
  <details className="mt-5 border-t border-line pt-4"><summary className="text-sm font-medium text-secondary">Advanced performance analytics</summary>
   <div className="mt-4 flex flex-wrap items-end gap-3"><label className="text-xs text-muted">Analytical series<select aria-label="Analytical series" className={cn(field,'mt-1 block')} value={analyticsSource} onChange={e=>setAnalyticsSource(e.target.value as typeof analyticsSource)}><option value="portfolio">Portfolio · {method}</option><option value="benchmark">Benchmark · {benchmarkId}</option></select></label><label className="text-xs text-muted">Annual risk-free rate (%)<input type="number" min="-10" max="50" step="0.1" className={cn(field,'mt-1 block w-28')} value={rf*100} onChange={e=>{const n=Number(e.target.value);if(Number.isFinite(n)&&n>=-10&&n<=50)setRf(n/100);}}/></label></div>
   <p className="mt-3 text-xs text-muted">Analytics below describe the selected {analyticsSource} series, not both. Rolling windows count observed periods. The risk-free rate is a user assumption, not a live rate. Irregular or short series do not produce annualized risk statistics.</p>
   <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">{[['Sharpe ratio',statistics(source,frequency,rf).sharpe],['Sortino ratio',statistics(source,frequency,rf).sortino],['Portfolio beta',matched?comparison.beta:null],['Information ratio',matched?comparison.information:null]].map(([label,value])=><div key={String(label)}><dt className="text-xs text-muted">{label}</dt><dd className="mt-1 text-base font-semibold tabular-nums text-ink">{typeof value==='number'&&Number.isFinite(value)?value.toFixed(2):'Unavailable'}</dd></div>)}</dl>
   <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2"><MiniChart title={`${analyticsSource==='portfolio'?'Portfolio':benchmarkId} drawdown`} lines={[{name:'Drawdown',color:'#b4232c',points:draw}]} /><MiniChart title="Rolling annualized volatility" lines={vols}/>
    <section className="rounded-xl border border-line p-4"><h4 className="text-sm font-semibold text-ink">Monthly returns heatmap</h4><p className="mt-1 text-xs text-muted">Month-end to month-end returns; the initial partial month is omitted.</p><div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4">{months.map(m=><div key={m.month} className={cn('rounded-lg p-2 text-center text-xs',m.value>=0?'bg-positive-soft text-positive':'bg-negative-soft text-negative')}><span className="block">{m.month}</span><span className="mt-1 block font-semibold tabular-nums">{m.value>0?'+':''}{m.value.toFixed(2)}%</span></div>)}</div>{!months.length&&<p className="mt-6 text-xs text-muted">Requires observations across at least two month ends.</p>}</section><MiniChart title="Rolling Sharpe ratio · 63 observations" unit="" lines={[{name:'Sharpe',color:'#6941a5',points:sharpe}]} /></div>
   <p className="mt-4 text-xs text-muted">Maximum drawdown: {source.length>1?pct(recover.worst):'Unavailable'} · Longest observed drawdown: {source.length>1?`${Math.round(recover.maxDays)} calendar days`:'Unavailable'} · {recover.episodes.filter(e=>e.end===null).length?'Recovery still open at the last observation.':'No unrecovered drawdown recorded.'}</p>
   <details className="mt-4"><summary className="text-xs text-secondary">Drawdown recovery periods</summary><div className="mt-2 max-h-48 overflow-auto"><table className="w-full text-left text-xs"><thead><tr><th>Previous peak UTC</th><th>Recovery UTC</th><th>Calendar days</th></tr></thead><tbody>{recover.episodes.map((episode,i)=><tr key={i} className="border-t border-line"><td className="py-2">{formatDate(episode.start)}</td><td>{episode.end===null?'Not recovered at last observation':formatDate(episode.end)}</td><td>{Math.round(episode.days)}</td></tr>)}</tbody></table></div></details>
   <details className="mt-4"><summary className="text-xs text-secondary">View analytical observations</summary><div className="mt-2 max-h-64 overflow-auto"><table className="w-full text-left text-xs tabular-nums"><thead><tr><th>Date UTC</th><th>Index</th><th>Drawdown %</th><th>30-period vol %</th><th>60-period vol %</th><th>90-period vol %</th><th>63-period Sharpe</th></tr></thead><tbody>{source.map((p,i)=><tr key={p.time} className="border-t border-line"><td className="py-2">{formatDate(p.time)}</td><td>{p.value.toFixed(4)}</td><td>{draw[i]?.value.toFixed(2)}</td>{vols.map(v=><td key={v.name}>{exact(v.points,p.time)?.value.toFixed(2)??'Unavailable'}</td>)}<td>{exact(sharpe,p.time)?.value.toFixed(2)??'Unavailable'}</td></tr>)}</tbody></table></div></details>
  </details>
  <details className="mt-5 border-t border-line pt-4"><summary className="text-xs text-muted">View recorded chart data &amp; calculation notes</summary><p className="mt-3 text-xs text-muted">Portfolio return method: {method}. TWR/MWR are consumed from archived reports; no reports are generated by viewing this chart. Excess return and beta need common dates and currencies. Volatility uses sample standard deviation and 252/52/12 observations per year for daily/weekly/monthly data. Annualized return requires at least one year. Benchmark source: {benchmark?.retrieved_at||'Unavailable'}.</p><div className="mt-3 max-h-60 overflow-auto"><table className="w-full text-left text-xs tabular-nums"><thead><tr><th>Date UTC</th><th>Series</th><th>Value / units</th></tr></thead><tbody>{lines.flatMap(l=>l.points.map(p=><tr key={`${l.name}-${p.time}`} className="border-t border-line"><td className="py-2">{new Date(p.time).toISOString()}</td><td>{l.name}</td><td>{p.value.toFixed(4)} {mode==='nav'?(l.name===benchmarkId?'index':currency):'%'}</td></tr>))}</tbody></table></div></details>
  <ModalSurface open={!!event} onClose={()=>setEvent(null)} label="Portfolio chart event"><div className="p-6"><h3 className="text-lg font-semibold text-ink">{event?.event_title}</h3><p className="mt-2 text-xs text-muted">{event?.occurrence_time} · {event?.event_category}</p><p className="mt-4 text-sm text-secondary">{event?.event_description||'No additional description recorded.'}</p>{!!event?.details&&<pre className="mt-4 overflow-auto text-xs">{JSON.stringify(event.details,null,2)}</pre>}<button type="button" className={cn(button,'mt-5')} onClick={()=>setEvent(null)}>Close event</button></div></ModalSurface>
 </section>;
}
