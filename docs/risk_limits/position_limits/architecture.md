# M11.02 — Position Limits: Architecture Specification

## 1. Executive Summary & Purpose

Module **M11.02 — Position Limits** delivers institutional-grade position-level exposure restrictions across individual securities, listings, and aggregated corporate issuers within the **Institutional Portfolio Risk Dashboard**.

Its primary objective is to prevent excessive concentration in individual securities or single issuers by enforcing configurable boundaries based on:
1. **Maximum Position Weight (% of NAV):** Limits position market value relative to total portfolio NAV.
2. **Absolute Notional Exposure:** Currency-denominated caps ($N_i = |MV_i|$) in USD, INR, or other ISO currencies.
3. **Long & Short Separation:** Isolated limits for long-only or short-only positions without masking concentration through netting.
4. **Issuer-Level Aggregation:** Multi-share-class, multi-listing aggregation consolidating gross economic concentration ($AMV_e = \sum |MV_i|$) and net exposure ($NMV_e = \sum MV_i$).
5. **Proposed-Order Pre-Trade Evaluation:** Simulation of hypothetical post-trade quantities and notionals feeding downstream pre-trade controls (M11.07).
6. **Breach Detection & Escalation:** Generates immutable breach events with severity classification feeding downstream escalation workflows (M11.08).

---

## 2. Mathematical Foundation & Exposure Conventions

### 2.1 Position Weight Calculation
For a position $i$ with signed market value $MV_i$ and portfolio net asset value $NAV_p$:
- **Absolute Position Weight:**
  $$AW_i = \frac{|MV_i|}{NAV_p} \times 100$$
- **Signed Position Weight:**
  $$W_i = \frac{MV_i}{NAV_p} \times 100$$

*Fail-Safe Rule:* If $NAV_p \le 0$, the evaluation terminates with an `INVALID_NAV` error status; zero or negative NAV is never treated as a valid pass.

### 2.2 Directional Exposure Isolation
- **Long Exposure:**
  $$MV_i^{\text{long}} = \max(MV_i, 0)$$
  $$W_i^{\text{long}} = \frac{MV_i^{\text{long}}}{NAV_p} \times 100$$
- **Short Exposure:**
  $$MV_i^{\text{short}} = \max(-MV_i, 0) \ge 0$$
  $$W_i^{\text{short}} = \frac{MV_i^{\text{short}}}{NAV_p} \times 100$$

### 2.3 Issuer-Level Aggregation
For an issuer $e$ comprising constituent instruments and listings $i \in e$:
- **Gross Economic Concentration:**
  $$AMV_e = \sum_{i \in e} |MV_i|$$
  $$W_e^{\text{gross}} = \frac{AMV_e}{NAV_p} \times 100$$
- **Signed Net Exposure:**
  $$NMV_e = \sum_{i \in e} MV_i$$
  $$W_e^{\text{net}} = \frac{NMV_e}{NAV_p} \times 100$$
- **Long and Short Issuer Aggregates:**
  $$LMV_e = \sum_{i \in e} \max(MV_i, 0), \quad SMV_e = \sum_{i \in e} \max(-MV_i, 0)$$

*Principle:* Direction-neutral concentration restrictions MUST evaluate against $AMV_e$ (Gross Concentration) and never against $NMV_e$ (Net Exposure).

### 2.4 Utilization & Headroom
For an evaluated exposure $E$, warning threshold $L_{\text{warn}}$, and hard threshold $L_{\text{hard}}$:
- **Hard Utilization:** $U_{\text{hard}} = \frac{E}{L_{\text{hard}}} \times 100$
- **Warning Utilization:** $U_{\text{warn}} = \frac{E}{L_{\text{warn}}} \times 100$
- **Remaining Capacity:** $\text{Capacity} = L_{\text{hard}} - E$
- **Breach Amount:** $\text{Breach} = \max(0, E - L_{\text{hard}})$

### 2.5 Proposed-Order Simulation (M11.07 Pre-Trade)
For order quantity $Q_{\text{order}}$ at reference price $P_{\text{ref}}$ and exchange rate $FX$:
- **BUY:** $Q_{\text{post}} = Q_{\text{current}} + Q_{\text{order}}$
- **SELL:** $Q_{\text{post}} = Q_{\text{current}} - Q_{\text{order}}$
- **Post Market Value:** $MV_{\text{post}} = Q_{\text{post}} \times P_{\text{ref}} \times FX$
- **Pre-Trade Approval Decision:** Approved if and only if all evaluated projected metrics remain $\le L_{\text{hard}}$.

---

## 3. Database Architecture & Tables

Integrated within PostgreSQL using SQLAlchemy 2.0 async models:
1. `m11_position_limit_configurations`: Limit configurations specifying limit type, direction, aggregation level, thresholds, precedence, and currency.
2. `m11_position_limit_profiles`: Reusable profiles (Standard, Moderate, Aggressive, Mandate-specific) containing bundled limits.
3. `m11_position_limit_assignments`: Scope-specific profile assignments to portfolios or mandates.
4. `m11_position_limit_evaluations`: Evaluation run header recording timestamps, portfolio NAV, base currency, and overall status.
5. `m11_position_limit_evaluation_results`: Granular evaluation result rows for each position, instrument, and issuer.
6. `m11_position_limit_breach_events`: Structured breach records with severity and cause for M11.08 consumption.
7. `m11_position_limit_audit_logs`: Append-only audit trail logging lifecycle and evaluation actions.
