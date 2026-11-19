import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import { createRefreshLoop } from '../utils/refreshLoop';
import type { RefreshSnapshot } from '../utils/refreshLoop';
const Context=createContext({enabled:true,setEnabled:(_value:boolean)=>{},generation:0,refreshAll:()=>{}});
export function LiveUpdatesProvider({children}:{children:React.ReactNode}) {
 const [enabled,setEnabled]=useState(true),[generation,setGeneration]=useState(0);
 return <Context.Provider value={{enabled,setEnabled,generation,refreshAll:()=>setGeneration(n=>n+1)}}>{children}</Context.Provider>;
}
export const useLiveUpdates=()=>useContext(Context);
export function useLiveRefresh(scope:string,job:(signal:AbortSignal)=>Promise<void>,interval=30000) {
 const settings=useLiveUpdates(),jobRef=useRef(job),loop=useRef<ReturnType<typeof createRefreshLoop>|null>(null);
 jobRef.current=job;
 const [state,setState]=useState<RefreshSnapshot>({running:false,lastChecked:null,lastSuccess:null,error:null});
 useEffect(()=>{
  setState({running:false,lastChecked:null,lastSuccess:null,error:null});
  const current=createRefreshLoop(signal=>jobRef.current(signal),setState,interval);loop.current=current;
  current.setEnabled(settings.enabled);
  const availability=()=>current.setActive(document.visibilityState==='visible'&&navigator.onLine);
  availability();current.start();
  document.addEventListener('visibilitychange',availability);window.addEventListener('online',availability);window.addEventListener('offline',availability);
  return()=>{current.dispose();if(loop.current===current)loop.current=null;document.removeEventListener('visibilitychange',availability);window.removeEventListener('online',availability);window.removeEventListener('offline',availability);};
 },[scope,interval]);
 useEffect(()=>loop.current?.setEnabled(settings.enabled),[settings.enabled]);
 const previous=useRef(settings.generation);
 useEffect(()=>{if(previous.current!==settings.generation){previous.current=settings.generation;loop.current?.refresh();}},[settings.generation]);
 return {...state,refresh:()=>loop.current?.refresh(),enabled:settings.enabled};
}
export function LiveUpdateControls(){
 const {enabled,setEnabled,refreshAll}=useLiveUpdates();const [available,setAvailable]=useState(true);
 useEffect(()=>{const update=()=>setAvailable(document.visibilityState==='visible'&&navigator.onLine);update();document.addEventListener('visibilitychange',update);window.addEventListener('online',update);window.addEventListener('offline',update);return()=>{document.removeEventListener('visibilitychange',update);window.removeEventListener('online',update);window.removeEventListener('offline',update);};},[]);
 return <div className="flex flex-wrap items-center gap-3 text-xs text-muted"><label className="flex items-center gap-1.5"><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)} className="accent-brand"/>Auto refresh · 30s</label><span>{!available?'Paused · offline or tab hidden':!enabled?'Paused':'Polling · provider data may be delayed'}</span><button type="button" onClick={refreshAll} disabled={!available} className="rounded-lg border border-line bg-surface px-3 py-2 text-xs font-medium text-secondary">Refresh now</button></div>;
}
