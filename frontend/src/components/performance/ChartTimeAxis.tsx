import React, { useEffect, useRef, useState } from 'react';

/** Calendar ticks describe the time scale only; no price data is filled or resampled. */
export function chartTimeTicks(start:number,end:number,count:number) {
 if(!Number.isFinite(start)||!Number.isFinite(end))return [];
 const span=end-start;
 const full=(t:number)=>new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(t);
 if(span<=0)return [{time:start,label:full(start),detail:new Date(start).toISOString()}];
 const day=86400000,monthMode=span>=90*day;
 const ticks:number[]=[];
 if(monthMode){
  const monthSpan=span/(30.4375*day);
  const step=[1,2,3,6,12,24,60].find(n=>monthSpan/n<=count-1)||120;
  const date=new Date(start),index=date.getUTCFullYear()*12+date.getUTCMonth();
  let next=Math.ceil(index/step)*step;
  let time=Date.UTC(Math.floor(next/12),next%12,1);
  if(time<start){next+=step;time=Date.UTC(Math.floor(next/12),next%12,1);}
  for(let i=0;time<=end&&i<30;i++,next+=step,time=Date.UTC(Math.floor(next/12),next%12,1))ticks.push(time);
 }else{
  const options=span<=day?[1,5,15,30,60,120,240,360,720].map(n=>n*60000):[1,2,7,14,30].map(n=>n*day);
  const step=options.find(n=>span/n<=count-1)||options[options.length-1];
  for(let time=Math.ceil(start/step)*step,i=0;time<=end&&i<30;time+=step,i++)ticks.push(time);
 }
 if(ticks.length<2)return [start,end].map(time=>({time,label:span<=day?new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'UTC'}).format(time):full(time),detail:new Date(time).toISOString()}));
 return ticks.map(time=>({time,label:new Intl.DateTimeFormat(span<=day?'en-GB':'en-US',span<=day?{hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'UTC'}:monthMode?{month:'short',year:'numeric',timeZone:'UTC'}:{month:'short',day:'numeric',timeZone:'UTC'}).format(time),detail:new Date(time).toISOString()}));
}
export function ChartTimeAxis({start,end,observations}:{start:number;end:number;observations:number}) {
 const ref=useRef<HTMLDivElement>(null),[width,setWidth]=useState(600);
 useEffect(()=>{const el=ref.current;if(!el)return;const observer=new ResizeObserver(entries=>setWidth(entries[0].contentRect.width));observer.observe(el);return()=>observer.disconnect();},[]);
 const count=Math.max(2,Math.min(8,Math.floor(width/85)));
 const ticks=chartTimeTicks(start,end,count);
 const full=(time:number)=>new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(time);
 return <div className="mt-1" aria-label="Chart time axis, UTC">
  <div ref={ref} className="relative h-10 border-t border-line" style={{marginLeft:'6.0465%',marginRight:'10.2326%'}}>
   {ticks.map(tick=>{const position=end>start?(tick.time-start)/(end-start)*100:0;return <div key={tick.time} className="absolute top-0" style={{left:`${position}%`}}><span aria-hidden="true" className="absolute left-0 top-0 h-1.5 border-l border-line-strong"/><time dateTime={tick.detail} title={tick.detail} className="absolute top-3 whitespace-nowrap text-xs font-medium tabular-nums text-secondary" style={{transform:position<8?'none':position>92?'translateX(-100%)':'translateX(-50%)'}}>{tick.label}</time></div>;})}
  </div>
  <div className="mt-1 flex flex-wrap justify-between gap-x-3 gap-y-1 text-xs text-muted"><span>{full(start)}{full(end)!==full(start)?` – ${full(end)}`:''} · UTC</span><span className="tabular-nums">{observations.toLocaleString()} {observations===1?'observation':'observations'}</span></div>
 </div>;
}
