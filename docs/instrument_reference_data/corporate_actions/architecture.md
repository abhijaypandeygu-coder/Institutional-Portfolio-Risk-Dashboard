# M04.03 Corporate Actions Engine Architecture

## 1. Overview
The **M04.03 Corporate Actions** submodule provides an institutional-grade event registry, versioning framework, factor calculation engines, and deterministic audit lineage for equities corporate actions within the *Institutional Portfolio Risk Dashboard*.

### Key Design Tenets
1. **Separation of Raw vs. Adjusted Metrics:** Raw historical market data (from M02) remains strictly immutable. Adjusted price and share series are computed as dynamic point-in-time transformations using deterministic runs and lineage records.
2. **Exact Decimal Precision:** Binary floating-point arithmetic is banned. All ratio, dividend, and compounding factor calculations execute via Python `Decimal` with `ROUND_HALF_EVEN` up to 12 decimal places.
3. **Exact Mathematical Reciprocity:** For non-cash distributions (splits, reverse splits, bonus issues), the product of the price factor and quantity factor is strictly unitary:
   $$F_P \times F_Q = 1.0$$
4. **Canonical Identity Binding:** Corporate action records attach strictly to canonical `instrument_id` (`INST_xxx`) in M04.01 (`m04_instruments`).
5. **Auditable Lineage:** Every adjustment computation produces a `run_id` accompanied by step-by-step lineage records detailing the event, version, unadjusted price, step factor, adjusted price, unadjusted quantity, step quantity factor, adjusted quantity, and formula descriptions.

---

## 2. Event Lifecycle & Taxonomy
Corporate actions transition through a strictly governed lifecycle state machine:
- `ANNOUNCED`: Proposed event details with preliminary dates and terms.
- `CONFIRMED`: Finalized exchange terms with established ex-date.
- `EFFECTIVE`: Event has passed ex-date and applies to historical time series adjustments.
- `CANCELLED`: Voided event, excluded from adjustments.
- `SUPERSEDED`: Replaced by an amended event version.

---

## 3. Supported Corporate Action Types & Formulas

### 3.1 Stock Splits & Reverse Splits
Given a split ratio $r = \frac{\text{Numerator}}{\text{Denominator}}$:
- **Quantity Factor ($F_Q$):** $r$
- **Price Factor ($F_P$):** $\frac{1}{r}$

*Example (2:1 Split):* Numerator = 2, Denominator = 1 $\implies F_Q = 2.0, F_P = 0.5$.
*Example (1:10 Reverse Split):* Numerator = 1, Denominator = 10 $\implies F_Q = 0.1, F_P = 10.0$.

### 3.2 Bonus Issues
Shareholders receive $b$ additional shares for every $a$ existing shares held:
- **Quantity Factor ($F_Q$):** $\frac{a + b}{a} = 1 + \frac{b}{a}$
- **Price Factor ($F_P$):** $\frac{a}{a + b} = \frac{1}{1 + b/a}$

*Example (1-for-4 Bonus):* $b = 1, a = 4 \implies F_Q = \frac{5}{4} = 1.25, F_P = \frac{4}{5} = 0.8$.

### 3.3 Cash Dividends
For an unadjusted pre-event closing price $P_t$ and dividend distribution $D$:
- **Effective Dividend ($D_{\text{eff}}$):** $D \times (1 - \text{tax\_rate})$ if net basis else $D$.
- **Price Factor ($F_P$):** $\frac{P_t - D_{\text{eff}}}{P_t}$
- **Quantity Factor ($F_Q$):** $1.0$ (share counts do not change).

### 3.4 Mergers & Successor Securities
Supports stock-for-stock, cash-only, and mixed considerations:
- Maps target instrument to successor instrument via `CorporateActionInstrument` (`SUCCESSOR_SECURITY`).
- Applies conversion ratios for share counts and pricing.

---

## 4. Cumulative Compounding Engine
When an instrument experiences multiple corporate actions over time, adjustments compound chronologically:
$$F_{\text{cumulative price}} = \prod_{i=1}^n F_{P, i}$$
$$G_{\text{cumulative quantity}} = \prod_{i=1}^n F_{Q, i}$$

---

## 5. Database Schema
- `corporate_actions`: Canonical event registry and lifecycle metadata.
- `corporate_action_instruments`: Role mappings (`ORIGINAL_SECURITY`, `SUCCESSOR_SECURITY`).
- `corporate_action_versions`: Immutable snapshot trail for event amendments.
- `corporate_action_dividends`: Gross/net dividend specifics.
- `corporate_action_ratios`: Exact integer terms for splits, reverse splits, and bonuses.
- `corporate_action_mergers`: Successor mapping, conversion ratios, and cash consideration.
- `corporate_action_adjustment_runs`: Audit runs with input/output SHA-256 checksums.
- `corporate_action_adjustment_lineage`: Step-by-step audit lineage per adjusted observation.

