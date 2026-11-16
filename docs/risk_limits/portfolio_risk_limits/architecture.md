# M11.01 — Portfolio Risk Limits: Architecture Specification

## 1. Executive Summary & Purpose

Module **M11.01 — Portfolio Risk Limits** provides an institutional-grade, policy-driven risk boundary and utilization monitoring framework within the **Institutional Portfolio Risk Dashboard**.

The module establishes configurable, version-controlled, and enforceable portfolio-wide risk boundaries for key quantitative risk measures:
1. **Value-at-Risk (VaR) Limits:** Absolute monetary and NAV-relative thresholds categorized by confidence levels (95%, 99%), risk horizons (1d, 10d, 20d), and calculation methodologies (Historical, Parametric, Monte Carlo).
2. **Volatility Limits:** Maximum permitted annualized portfolio volatility (realized and forecast).
3. **Drawdown Limits:** Peak-to-trough drawdown magnitude warning and hard limits with high-water mark tracking.
4. **Risk Limit Profiles:** Reusable, versioned profiles (Standard, Conservative, Moderate, Aggressive, Mandate-specific) governing multi-metric policies.
5. **Precedence-driven Assignments:** Deterministic assignment binding (Portfolio > Mandate > Default) ensuring single-point-of-truth active policy mapping.
6. **Limit Utilization Engine:** Computes warning and hard utilization ($U = R / L$), remaining headroom ($L - R$), implied monetary limits for percentage thresholds, and boundary state classification (`WITHIN_LIMIT`, `WARNING`, `HARD_LIMIT_EXCEEDED`, `UNAVAILABLE`, `STALE`, `INVALID`).

---

## 2. Mathematical Foundation & Formulae

### 2.1 Threshold Utilization & Headroom
For an observed metric value $R$, warning threshold $L_{\text{warn}}$, and hard threshold $L_{\text{hard}}$ ($L_{\text{hard}} \ge L_{\text{warn}} > 0$):

$$\text{Utilization}_{\text{warning}} = \frac{R}{L_{\text{warn}}} \times 100$$

$$\text{Utilization}_{\text{hard}} = \frac{R}{L_{\text{hard}}} \times 100$$

$$\text{Headroom}_{\text{hard}} = L_{\text{hard}} - R$$

### 2.2 NAV-Relative VaR Evaluation
For NAV-relative VaR limits parameterized in percentage of NAV ($L_{\text{warn}}\%$, $L_{\text{hard}}\%$):

$$VaR_{\text{rel}} = \frac{VaR_{\text{monetary}}}{NAV} \times 100$$

$$\text{Implied Hard Monetary Limit} = NAV \times \frac{L_{\text{hard}}}{100}$$

$$\text{Monetary Headroom} = \text{Implied Hard Monetary Limit} - VaR_{\text{monetary}}$$

*Fail-Safe Rule:* If $NAV \le 0$, evaluation is flagged as `INVALID` with diagnostic error rather than throwing zero-division or emitting false passes.

### 2.3 Drawdown Magnitude
Drawdown magnitude is treated as a strictly non-negative percentage representing loss from peak:

$$D_t = -DD_t = \frac{H_t - V_t}{H_t} \ge 0$$

Where $H_t$ is the historical High-Water Mark (peak NAV) and $V_t$ is the current portfolio valuation.

### 2.4 Precedence and State Aggregation
When evaluating multiple limits for a portfolio:
1. `HARD_LIMIT_EXCEEDED` takes top precedence: if any active limit is breached, the portfolio status is `HARD_LIMIT_EXCEEDED`.
2. `WARNING` takes second precedence: if no hard limits are breached but one or more warning limits are breached, overall status is `WARNING`.
3. `INVALID` / `UNAVAILABLE` / `STALE`: if any input is missing or malformed, the portfolio is flagged and cannot be classified as `WITHIN_LIMIT`.
4. `WITHIN_LIMIT`: all active evaluated limits have $R < L_{\text{warn}}$.

---

## 3. Database Schema

Tables created in database schema:
- `risk_limit_profiles`: Profile definitions with metadata, status (`DRAFT`, `APPROVED`, `ACTIVE`, `SUSPENDED`, `RETIRED`), and base currency policies.
- `risk_limit_profile_versions`: Immutable version records with audit stamps (`version_number`, `effective_from`, `effective_to`).
- `portfolio_risk_limits`: Policy rules specifying metric identifier, category, threshold type, comparison operator, warning/hard values, and methodology metadata.
- `portfolio_limit_assignments`: Mapping between profiles and targets (portfolios/mandates) with precedence rules.
- `risk_limit_utilization_snapshots`: Historical and latest audit snapshots capturing evaluation results, utilization percentages, headroom, and detailed breakdown.
- `risk_limit_audit_logs`: Append-only audit trail logging state transitions, approvals, activations, and assignment changes.
