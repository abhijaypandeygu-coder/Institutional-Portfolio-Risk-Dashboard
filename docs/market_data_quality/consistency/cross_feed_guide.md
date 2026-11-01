# Cross-Feed Comparison & Source Eligibility Guide

## 1. Principles of Independent Source Verification
Cross-feed comparison provides assurance that prices published by a market data feed are not distorted by network corruption, local server lag, or faulty vendor ticker plants.

However, an institutional engine must prevent **false comparisons**:
1. **Instrument Identity:** Never compare an ADR listing against a domestic listing without exchange and currency adjustments.
2. **Currency:** Never compare Indian Rupee (INR) prices against US Dollar (USD) prices directly.
3. **Observation Type:** Never compare a closing daily candle against a real-time Level 1 quote midpoint.
4. **Time Alignment:** Feeds must publish within a tight millisecond window (default 5000ms) to ensure volatility does not mimic source discrepancy.
5. **Real vs. Simulated Isolation:** Real market data (e.g. Alpha Vantage) must never be compared against simulated data (e.g. M02 Simulator) as if the simulator were an actual independent verification.
