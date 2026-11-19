import test from 'node:test';
import assert from 'node:assert/strict';
import { excessUnavailableReason, axisDomain, timestamp, aggregate, clean, drawdown, indexed, monthly, relative, statistics, rolling } from '../src/utils/performanceAnalytics.ts';
const day=86400000;
const rows=(values:number[])=>values.map((value,i)=>({time:Date.UTC(2025,0,1)+i*day,value}));
test('drawdown tracks the running peak and full capital loss',()=>{assert.deepEqual(drawdown(rows([100,120,90,126,0])).map(p=>Math.round(p.value)),[0,0,-25,0,-100]);});
test('does not annualize a short or irregular history',()=>{assert.equal(statistics(rows([100,105]),'DAILY').annualized,null);const sparse=rows(Array.from({length:25},(_,i)=>100+i)).map((p,i)=>({...p,time:p.time+i*10*day}));assert.equal(statistics(sparse,'DAILY').volatility,null);});
test('annual return is based on actual elapsed days',()=>{assert.ok(Math.abs(statistics([{time:0,value:100},{time:365*day,value:121}],'DAILY').annualized!-.21)<1e-12);});
test('zero is not replaced or dropped and return can be minus 100%',()=>{assert.equal(clean(rows([100,0])).length,2);assert.equal(statistics(clean(rows([100,0])),'DAILY').total,-1);assert.equal(statistics(rows([0,100]),'DAILY').total,null);});
test('normalizes from the starting observation, never the ending NAV',()=>{assert.deepEqual(indexed(rows([200,220])).map(p=>p.value),[100,110.00000000000001]);});
test('comparison requires common observed dates',()=>{const p=rows([100,110,121]),b=rows([100,104,108]);assert.ok(Math.abs(relative(p,b,'DAILY').total!-.13)<1e-12);assert.equal(relative(p,b.map(x=>({...x,time:x.time+100*day})),'DAILY').total,null);});
test('aggregates end-of-period observations without filling dates',()=>{const p=[{time:Date.UTC(2025,0,1),value:100},{time:Date.UTC(2025,0,31),value:110},{time:Date.UTC(2025,2,31),value:121}];assert.equal(aggregate(p,'MONTHLY').length,2);assert.deepEqual(monthly(p),[]);});
test('rolling risk has no placeholder values or divide-by-zero Sharpe',()=>{assert.deepEqual(rolling(rows([100,101]),30,'DAILY','volatility'),[]);assert.equal(statistics(rows(Array(30).fill(100)),'DAILY').sharpe,null);});

test('negative NAV observations are not silently dropped',()=>{assert.equal(clean(rows([100,-20])).length,2);assert.equal(statistics(clean(rows([100,-20])),'DAILY').total,-1.2);assert.equal(statistics([{time:0,value:100},{time:365*day,value:-20}],'DAILY').annualized,null);});

test('legacy backend timestamps use UTC and provider offsets are retained',()=>{assert.equal(timestamp('2026-01-01T12:00:00'),Date.UTC(2026,0,1,12));assert.equal(timestamp('2026-01-01T12:00:00+05:30'),Date.UTC(2026,0,1,6,30));});

test('single NAV record is centred on a consistent axis',()=>{const d=axisDomain([187083]);assert.ok(d.min<187083&&d.max>187083);assert.ok(Math.abs((187083-d.min)/d.span-.5)<1e-9);});
test('NAV and benchmark can use independent domains without false rescaling',()=>{const nav=axisDomain([187083]),benchmark=axisDomain([100,110]);assert.ok(nav.min>100000);assert.ok(benchmark.max<120);assert.deepEqual(axisDomain([]),{min:0,max:1,span:1});});

test('excess view explains each missing prerequisite',()=>{assert.match(excessUnavailableReason('TWR',0,251,true,0)!,/complete TWR report/);assert.match(excessUnavailableReason('NAV',1,251,true,1)!,/two recorded/);assert.match(excessUnavailableReason('TWR',30,0,true,0)!,/benchmark observations/);assert.match(excessUnavailableReason('TWR',30,30,false,0)!,/currencies/);assert.match(excessUnavailableReason('TWR',30,30,true,1)!,/common observed/);assert.match(excessUnavailableReason('MWR',30,30,true,30)!,/period summary/);});
test('excess view is available with matching history and currency',()=>{assert.equal(excessUnavailableReason('TWR',30,30,true,30),null);assert.equal(excessUnavailableReason('NAV',2,30,true,2),null);});
