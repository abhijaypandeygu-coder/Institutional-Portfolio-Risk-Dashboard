// Backend historical timestamps are documented as UTC, including legacy naive ISO strings.
export function timestamp(value: string) { if(typeof value!=='string')return NaN;return Date.parse(/^\d{4}-\d{2}-\d{2}T/.test(value)&&!/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)?value+'Z':value); }
export type Observation = { time: number; value: number; nav?: number };
export type Frequency = 'DAILY' | 'WEEKLY' | 'MONTHLY';
export const finite = (v: unknown): number | null => v !== null && v !== undefined && v !== '' && (typeof v === 'number' || typeof v === 'string') && Number.isFinite(Number(v)) ? Number(v) : null;
export function clean(rows: Observation[]) { return [...new Map(rows.filter(p => Number.isFinite(p.time) && Number.isFinite(p.value) ).sort((a,b) => a.time-b.time).map(p=>[p.time,p])).values()]; }
export function aggregate(rows: Observation[], frequency: Frequency) {
  const groups = new Map<string, Observation>();
  clean(rows).forEach(p=>{ const d=new Date(p.time); let k=d.toISOString().slice(0,10); if(frequency==='MONTHLY') k=k.slice(0,7); if(frequency==='WEEKLY') { const day=d.getUTCDay()||7; d.setUTCDate(d.getUTCDate()-day+1); k=d.toISOString().slice(0,10); } groups.set(k,p); });
  return [...groups.values()];
}
export function indexed(rows: Observation[]) { const base=rows[0]?.value; return base>0?rows.map(p=>({...p,value:p.value/base*100})):[]; }
export function returns(rows: Observation[]) { return rows.slice(1).flatMap((p,i)=>rows[i].value>0?[{...p,value:p.value/rows[i].value-1}]:[]); }
const mean=(v:number[])=>v.reduce((a,b)=>a+b,0)/v.length;
export function deviation(v:number[]) { if(v.length<2)return null; const m=mean(v);return Math.sqrt(v.reduce((a,b)=>a+(b-m)**2,0)/(v.length-1)); }
export function drawdown(rows:Observation[]) { let peak=0; return rows.map(p=>{peak=Math.max(peak,p.value);return {...p,value:peak>0?(p.value/peak-1)*100:0};}); }
export function cadence(rows:Observation[], f:Frequency) {
  if(rows.length<2)return false;
  const gaps=rows.slice(1).map((p,i)=>(p.time-rows[i].time)/86400000);
  const [min,max]=f==='DAILY'?[.5,5]:f==='WEEKLY'?[2,12]:[15,45];
  return gaps.every(g=>g>=min&&g<=max);
}
export function statistics(rows:Observation[], f:Frequency, riskFree=0) {
  const r=returns(rows).map(p=>p.value), sd=deviation(r), factor=f==='DAILY'?252:f==='WEEKLY'?52:12;
  const days=rows.length>1?(rows[rows.length-1].time-rows[0].time)/86400000:0;
  const total=rows.length>1&&rows[0].value>0?rows[rows.length-1].value/rows[0].value-1:null;
  const eligible=r.length>=20&&r.length===rows.length-1&&cadence(rows,f), vol=eligible&&sd!==null?sd*Math.sqrt(factor):null;
  const periodRf=(1+riskFree)**(1/factor)-1;
  const downs=r.map(x=>Math.min(0,x-periodRf));const downside=r.length?Math.sqrt(mean(downs.map(x=>x*x))):0;
  return { total, annualized: total!==null&&total>=-1&&days>=365?(1+total)**(365/days)-1:null, volatility:vol,
    drawdown:rows.length>1&&rows[0].value>0?Math.min(...drawdown(rows).map(p=>p.value))/100:null,
    sharpe:eligible&&sd&&sd>0?(mean(r)-periodRf)/sd*Math.sqrt(factor):null,
    sortino:eligible&&downside>0?(mean(r)-periodRf)/downside*Math.sqrt(factor):null,
    count:r.length, days };
}
// Match observed calendar dates only; no forward fill, interpolation, or comparison of disjoint windows.
export function align(a:Observation[],b:Observation[]) {
  const bm=new Map(b.map(p=>[new Date(p.time).toISOString().slice(0,10),p]));
  const pairs=a.flatMap(p=>{const q=bm.get(new Date(p.time).toISOString().slice(0,10));return q?[{a:p,b:q}]:[];});
  return {a:pairs.map(p=>p.a),b:pairs.map(p=>({...p.b,time:p.a.time}))};
}
export function relative(a:Observation[],b:Observation[],f:Frequency) {
  const aligned=align(a,b), ai=indexed(aligned.a),bi=indexed(aligned.b);
  const excess=ai.map((p,i)=>({...p,value:p.value-bi[i].value}));
  const ar=returns(ai).map(p=>p.value),br=returns(bi).map(p=>p.value),sd=deviation(ar.map((v,i)=>v-br[i]));
  const factor=f==='DAILY'?252:f==='WEEKLY'?52:12;
  let beta:number|null=null,information:number|null=null;
  if(ar.length>=20&&ar.length===br.length&&ar.length===ai.length-1&&cadence(ai,f)) { const am=mean(ar),bm=mean(br); const variance=br.reduce((s,v)=>s+(v-bm)**2,0); beta=variance>0?ar.reduce((s,v,i)=>s+(v-am)*(br[i]-bm),0)/variance:null; information=sd&&sd>0?mean(ar.map((v,i)=>v-br[i]))/sd*Math.sqrt(factor):null; }
  return {aligned,excess,total:excess.length>1?excess[excess.length-1].value/100:null,beta,information};
}
export function rolling(rows:Observation[],window:number,f:Frequency,mode:'volatility'|'sharpe',rf=0):Observation[] {
  const out:Observation[]=[]; for(let i=window;i<rows.length;i++){ const slice=rows.slice(i-window,i+1);const stat=statistics(slice,f,rf);const value=stat[mode];if(value!==null&&Number.isFinite(value))out.push({time:rows[i].time,value:mode==='volatility'?value*100:value});}return out;
}
export function monthly(rows:Observation[]) {
  const ends=aggregate(rows,'MONTHLY'); return ends.slice(1).flatMap((p,i)=>{const current=new Date(p.time),previous=new Date(ends[i].time); const months=(current.getUTCFullYear()-previous.getUTCFullYear())*12+current.getUTCMonth()-previous.getUTCMonth();return months===1&&ends[i].value>0?[{month:current.toISOString().slice(0,7),value:(p.value/ends[i].value-1)*100}]:[];});
}
export function recovery(rows:Observation[]) {
  let peak=rows[0],start:Observation|null=null,worst=0,maxDays=0; const episodes:{start:number;end:number|null;days:number}[]=[];
  rows.forEach(p=>{ if(!peak||p.value>=peak.value){if(start){const days=(p.time-start.time)/86400000;episodes.push({start:start.time,end:p.time,days});maxDays=Math.max(maxDays,days);start=null;}peak=p;}else{if(!start)start=peak;worst=Math.min(worst,p.value/peak.value-1);} });
  if(start&&rows.length){const s=start as Observation,days=(rows[rows.length-1].time-s.time)/86400000;episodes.push({start:s.time,end:null,days});maxDays=Math.max(maxDays,days);}
  return {episodes,worst,maxDays};
}

// A constant series belongs at the centre of its axis, not at an artificial lower bound.
export function axisDomain(values:number[]) {
 const valid=values.filter(Number.isFinite);
 if(!valid.length)return {min:0,max:1,span:1};
 const low=Math.min(...valid),high=Math.max(...valid);
 const padding=low===high?Math.max(Math.abs(low)*.01,1):(high-low)*.05;
 const min=low-padding,max=high+padding;
 return {min,max,span:max-min};
}

export function excessUnavailableReason(method:string, portfolioCount:number, benchmarkCount:number, sameCurrency:boolean, alignedCount:number) {
 if(method==='MWR')return 'MWR is a period summary, not a dated return series. Select TWR with a complete archived report for excess-return history.';
 if(portfolioCount<2)return method==='NAV'?'At least two recorded portfolio NAV observations are needed for a NAV-change comparison.':'At least two cash-flow-adjusted portfolio observations from a complete TWR report are needed.';
 if(benchmarkCount<2)return 'At least two benchmark observations are needed. Choose a benchmark and period with available history.';
 if(!sameCurrency)return 'Portfolio and benchmark currencies must match. FX-adjusted comparison data is not available.';
 if(alignedCount<2)return 'At least two common observed calendar dates are needed. Choose a period that overlaps the portfolio history.';
 return null;
}
