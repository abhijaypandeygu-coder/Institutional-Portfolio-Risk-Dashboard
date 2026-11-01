# M03.07 Use Eligibility Guide

## 1. Calculation Profiles
Downstream financial models consume data with varying tolerance for imperfections. M03.07 provides four preconfigured use-eligibility profiles:

| Profile Code | Profile Name | Target Financial Modules | Score Thresholds (Rel / Comp / Fresh) | Hard Gate Mandates |
|---|---|---|---|---|
| `DAILY_VALUATION` | Daily Portfolio Valuation | Net Asset Value (NAV), Position Mark-to-Market | 90 / 95 / 80 | Price validity, Timestamp integrity |
| `HISTORICAL_VAR` | Historical Value at Risk | Parametric VaR, Historical Simulation, Expected Shortfall | 85 / 95 / 70 | Price validity, Cross-feed consistency |
| `SPREAD_CALCULATION` | Bid-Ask Spread Analytics | Liquidity cost models, Execution shortfall | 90 / 90 / 90 | Price validity, Book continuity, Capability |
| `ORDER_BOOK_IMBALANCE`| Order Book Microstructure | Queue dynamics, Depth imbalance, Execution alpha | 95 / 95 / 95 | Price validity, Book continuity, Sequence integrity |

---

## 2. Hard Gate Evaluation Order
Regardless of numeric score attainment, every evaluation evaluates hard gates first:
1. **Capability Gate:** Is the data type supported by the provider? If false $\rightarrow$ `NOT_SUPPORTED`.
2. **Price Validity Gate:** Did price validation fail? If failed $\rightarrow$ `REJECTED` (blocks all financial calculations).
3. **Timestamp Integrity Gate:** Did timestamp checks flag retrograde movement or drift? If failed $\rightarrow$ `REJECTED`.
4. **Order Book Continuity Gate:** Did order-book validation detect crossed books or gap deltas? If failed $\rightarrow$ `REJECTED` (for order book profiles) or `RESTRICTED`.
5. **Cross-Feed Consistency Gate:** Did M03.06 flag cross-feed deviation $> 2.0\%$? If failed $\rightarrow$ `RESTRICTED`.

---

## 3. Eligibility Status Classifications
- **`ACCEPTED`:** All hard gates passed and all quality scores meet or exceed target profile thresholds.
- **`ACCEPTED_WITH_WARNING`:** All hard gates passed; scores fall between warning thresholds and target thresholds. Data can be used with downstream risk logging.
- **`RESTRICTED`:** Non-critical validation or moderate score deficit prevents unconditional use. Allowed only in fallback or conservative scenarios.
- **`REJECTED`:** Critical hard gate failure or score below minimum tolerance. Strictly barred from production use.
- **`NOT_SUPPORTED`:** Provider does not support requested capability (e.g. streaming L2 order book requested from Alpha Vantage Free).

