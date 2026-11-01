# Module 03.02: Validation Rules & Numerical Integrity Guide

## 1. Rule Hierarchy and Enforcement Actions

The validation pipeline enforces rules in order of severity and priority:
1. **Mandatory Structural Validity:** Malformed numbers, non-finite values (NaN, +Inf, -Inf), and negative prices trigger immediate `REJECTED` status and halt subsequent movement checks.
2. **Instrument Conventions:** Minimum/maximum range violations, tick-size misalignment (e.g. 0.05 tick size violated by 100.03), and decimal precision overshoots trigger `REJECTED`.
3. **Zero Price Conventions:** Executable trade/LTP at zero is `REJECTED`. Quote bid/ask at zero returns `ACCEPTED_WITH_WARNING`. Alpha Vantage sentinel zero triggers `QUARANTINED`. Zero volume is preserved as `ACCEPTED`.
4. **Exchange Bands:** Breach of official upper or lower circuit bands triggers `QUARANTINED`.
5. **Extreme Movements:** Percentage movement breaches trigger `ACCEPTED_WITH_WARNING` unless an official circuit band breach occurred. Corporate actions flag the movement for review rather than quarantine.
6. **Reference & Cross-Source:** Multi-provider discrepancy exceeding configured tolerance triggers `QUARANTINED`. Currency mismatches trigger `QUARANTINED`.

---

## 2. Numerical Precision Standards

- **Decimal-Only Arithmetic:** Direct floating-point modulo (`price % tick_size`) is prohibited due to IEEE-754 binary floating-point rounding errors (e.g., `0.1 + 0.2 != 0.3`).
- **Tick Size Validation:** Evaluated using integer quantization:
  $$\text{quotient} = \frac{\text{Price}}{\text{Tick Size}}$$
  Valid if and only if $\text{quotient} = \text{round}(\text{quotient})$.
- **Percentage Change:**
  $$\text{Percentage Change} = \frac{\text{Current Price} - \text{Reference Price}}{\text{Reference Price}} \times 100$$
  Evaluated only when $\text{Reference Price} > 0$.
- **Cross-Source Discrepancy:**
  $$\text{Percentage Discrepancy} = \frac{|\text{Price}_A - \text{Price}_B|}{\max(\text{Price}_A, \text{Price}_B)} \times 100$$
