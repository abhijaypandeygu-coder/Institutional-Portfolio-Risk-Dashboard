import test from 'node:test';
import assert from 'node:assert/strict';
import { duration, imbalanceLabel, mergeDepthPoints, money, quantityImbalance, simulated, sourceAge, tierDistribution } from '../src/utils/liquidityAnalytics.ts';

test('tier distribution adds value weights, not instrument counts', () => {
  const result = tierDistribution([{liquidity_bucket:'TIER_1_HIGH',weight_pct:80}, {liquidity_bucket:'TIER_2_MODERATE',weight_pct:10}, {liquidity_bucket:'TIER_2_MODERATE',weight_pct:10}]);
  assert.equal(result[0].weight,80); assert.equal(result[1].weight,20);
});
test('tier weights preserve leverage and unknown classification', () => {
  const result=tierDistribution([{liquidity_bucket:'TIER_1_HIGH',weight_pct:120},{liquidity_bucket:'UNKNOWN',weight_pct:30}]);
  assert.equal(result[0].weight,120); assert.equal(result[4].weight,30);
});
test('positive leaning depth is not called balanced or buy pressure',()=>{
  assert.equal(imbalanceLabel(.178),'Bid-leaning (17.8%)'); assert.equal(imbalanceLabel(-.178),'Ask-leaning (-17.8%)'); assert.match(imbalanceLabel(.05),/Near-balanced/); assert.match(imbalanceLabel(.21),/Bid-heavy/);
});
test('quantity imbalance is computed over visible levels with empty book unavailable',()=>{
  assert.equal(quantityImbalance([{quantity:3}],[{quantity:1}]),.5); assert.equal(quantityImbalance([],[]),null);
});
test('source freshness uses source time and rejects a future clock',()=>{
  assert.equal(sourceAge('2026-01-01T00:00:00',Date.parse('2026-01-01T00:00:00.250Z')),'250 ms'); assert.equal(sourceAge(null),'Unavailable'); assert.equal(sourceAge('2026-01-02T00:00:00Z',Date.parse('2026-01-01T00:00:00Z')),'Clock mismatch');
});
test('depth history deduplicates source timestamps and caps retained observations',()=>{
  const p={timestamp:'2026-01-01T00:00:00Z',bid:100,ask:50}; assert.equal(mergeDepthPoints([p],[p]).length,1); assert.equal(mergeDepthPoints([],Array.from({length:600},(_,i)=>({timestamp:new Date(i*1000).toISOString(),bid:i,ask:i}))).length,500);
});
test('native INR formatting preserves zero without applying FX',()=>{
  assert.match(money(3500,'INR'),/₹/);assert.match(money(0,'USD'),/0\.00/); assert.equal(money(null,'INR'),'Unavailable');
});
test('trading duration distinguishes zero, sub-minute and different session lengths',()=>{
  assert.equal(duration(0),'No execution needed');assert.equal(duration(.1),'< 1 trading minute');assert.equal(duration(375),'6.25 trading hours');assert.equal(duration(390),'6.50 trading hours');
});
test('simulated and estimated sources are explicitly detected',()=>{
  assert.equal(simulated({venue:'LIVE_FEED'}),true);assert.equal(simulated({source_kind:'ESTIMATED'}),true);assert.equal(simulated({source_kind:'PROVIDER_REPORTED',venue:'UPSTOX/NSE_L2'}),false);
});
