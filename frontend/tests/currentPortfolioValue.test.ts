import test from 'node:test';
import assert from 'node:assert/strict';
import { currentPortfolioValue } from '../src/utils/currentPortfolioValue.ts';
const snapshot = (holdings: any[], weight_basis = 'Absolute position value; NAV unavailable', total_nav = 0) => ({ holdings, weight_basis, total_nav, reporting_currency: 'USD' }) as any;
test('current value changes with current holdings and preserves short signs', () => {
  const long = { position_direction: 'LONG', position_notional: 100 };
  const short = { position_direction: 'SHORT', position_notional: 25 };
  assert.equal(currentPortfolioValue(snapshot([long, short])).display, '$75.00');
  assert.equal(currentPortfolioValue(snapshot([long])).display, '$100.00');
  assert.equal(currentPortfolioValue(snapshot([])).display, '$0.00');
});
test('holdings value is not called NAV without a NAV denominator', () => {
  assert.equal(currentPortfolioValue(snapshot([])).label, 'Current holdings value');
  assert.equal(currentPortfolioValue(snapshot([], 'Portfolio NAV', 220)).display, '$220.00');
  assert.equal(currentPortfolioValue(snapshot([], 'Portfolio NAV', 220)).label, 'Current portfolio NAV');
});
test('missing or invalid current data is unavailable instead of old stored NAV', () => {
  assert.equal(currentPortfolioValue(null).display, 'Unavailable');
  assert.equal(currentPortfolioValue(snapshot([{position_notional: 'bad'}])).display, 'Unavailable');
});
