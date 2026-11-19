export type RefreshSnapshot = { running:boolean; lastChecked:number|null; lastSuccess:number|null; error:string|null };
type Clock = { now:()=>number; later:(fn:()=>void,ms:number)=>unknown; cancel:(id:unknown)=>void };
export function createRefreshLoop(job:(signal:AbortSignal)=>Promise<void>,notify:(s:RefreshSnapshot)=>void,interval=30000,clock:Clock={now:Date.now,later:(f,ms)=>setTimeout(f,ms),cancel:id=>clearTimeout(id as ReturnType<typeof setTimeout>)}) {
 let enabled=true,active=true,disposed=false,timer:unknown=null,controller:AbortController|null=null,failures=0;
 let state:RefreshSnapshot={running:false,lastChecked:null,lastSuccess:null,error:null};
 const publish=()=>{if(!disposed)notify({...state});};
 const clear=()=>{if(timer!==null){clock.cancel(timer);timer=null;}};
 const schedule=()=>{clear();if(!disposed&&enabled&&active&&!state.running)timer=clock.later(()=>void run(),Math.min(interval*2**Math.min(failures,2),120000));};
 async function run(){
  if(disposed||!active||state.running)return;
  clear();controller=new AbortController();const current=controller;
  state.running=true;publish();
  const timeout=clock.later(()=>current.abort(),45000);
  try {await job(current.signal);if(disposed||current.signal.aborted)throw new Error('Refresh timed out.');failures=0;state.lastSuccess=clock.now();state.error=null;}
  catch(e){if(!disposed){failures++;state.error=e instanceof Error?e.message:'Refresh failed.';}}
  finally{clock.cancel(timeout);if(!disposed){state.running=false;state.lastChecked=clock.now();publish();schedule();}}
 }
 return {
  start:()=>void run(), refresh:()=>void run(),
  setEnabled:(value:boolean)=>{enabled=value;if(!enabled)clear();else schedule();},
  setActive:(value:boolean)=>{const resumed=!active&&value;active=value;if(!active)clear();else if(resumed&&enabled)void run();},
  dispose:()=>{disposed=true;clear();controller?.abort();},
 };
}
