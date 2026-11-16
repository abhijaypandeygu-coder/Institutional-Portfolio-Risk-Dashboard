# M11.05 — Dynamic Limits: System Architecture

## 1. Overview and Purpose

The **Dynamic Limits (M11.05)** module is an institutional-grade component of the **Risk Limits & Control Framework (M11)**. It provides dynamic modulation of risk thresholds based on prevailing market regimes, real-time portfolio risk metrics, session schedules across Indian (`Asia/Kolkata`) and US (`America/New_York`) equity exchanges, and strict maker-checker governed manual overrides.

### Core Objectives
1. **Adaptive Boundary Management:** Automatically adjust portfolio and position boundaries in response to volatility shocks, liquidity dry-ups, or stressed market regimes.
2. **Restrictive-Only Convention:** Prevent unauthorized loosening of approved risk boundaries during live market trading. For upper limits (Caps), effective limits can only tighten ($\min(L_{base}, L_{adj})$); for lower limits (Floors), effective limits can only strengthen ($\max(L_{base}, L_{adj})$).
3. **Maker-Checker Manual Overrides:** Guarantee strict governance separation between override requestors and approvers, time-bounded validity, and comprehensive audit trail tracking.
4. **Deterministic Precedence Hierarchy:** Ensure unambiguous resolution when condition rules, time profiles, and manual overrides interact simultaneously.
5. **Immutable Effective Limit Snapshots:** Materialize calculation outputs into cryptographically signed snapshots (`SHA-256`) with complete metric and rule lineage for downstream consumption by **M11.07 Pre-Trade Risk Checks** and **M11.08 Breach Monitoring**.

---

## 2. Architecture & Component Hierarchy

```
┌────────────────────────────────────────────────────────────────────────┐
│                   M11.05 DYNAMIC LIMITS ENGINE                         │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌───────────────────────┐         ┌────────────────────────┐          │
│  │ Upstream Metric Inputs│         │ Trading Calendar / Tz  │          │
│  │ (M07 Vol, M09 Depth,  │         │ (M04.04, IST & EST     │          │
│  │  M08 Factors, Drawdown│         │  Session Mapping)      │          │
│  └───────────┬───────────┘         └───────────┬────────────┘          │
│              │                                 │                       │
│              ▼                                 ▼                       │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │           Dynamic Limit Service & Rule Evaluator         │          │
│  │                                                          │          │
│  │   • Condition Evaluator (Operators & Hysteresis Bands)   │          │
│  │   • Schedule Matcher (Pre-mkt, Open, Regular, Close)     │          │
│  │   • Maker-Checker Override Validator                     │          │
│  │   • Conflict Resolution & Restrictive-Only Clamping      │          │
│  └───────────────────────────┬──────────────────────────────┘          │
│                              │                                         │
│                              ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │              Effective Limit Snapshot Engine             │          │
│  │                                                          │          │
│  │   • Base vs Effective Threshold Determination            │          │
│  │   • Lineage Metadata Construction & SHA-256 Hashing      │          │
│  │   • Immutable Database Persistence                       │          │
│  └───────────────────────────┬──────────────────────────────┘          │
│                              │                                         │
└──────────────────────────────┼─────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Downstream Consumers:                                                  │
│   • M11.07 Pre-Trade Risk Engine (Real-Time Order Approval)            │
│   • M11.08 Breach Monitoring Engine (Alerts & Escalation Workflows)    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Mathematical Specifications

### 3.1 Adjustment Transformations
1. **Multiplicative Scaling:**
   $$L_{adj} = L_{base} \times A$$
2. **Additive Adjustment:**
   $$L_{adj} = L_{base} + \Delta L$$
3. **Absolute Replacement:**
   $$L_{adj} = V_{replacement}$$

### 3.2 Restrictive-Only Enforcement
- **Cap Constraints (e.g. Max Position Weight, Max VaR, Max Drawdown):**
  $$L_{eff} = \min(L_{base}, L_{adj})$$
- **Floor Constraints (e.g. Min Liquidity Score, Min Depth, Min Traded Volume):**
  $$L_{eff} = \max(L_{base}, L_{adj})$$

### 3.3 Hysteresis Band Logic
To eliminate limit thrashing during oscillating market conditions:
- **Upward Trigger (e.g. Volatility Spike):**
  $$\text{State}_{t} = \begin{cases} 
  \text{Active} & \text{if } V_t \ge T_{entry} \\
  \text{Inactive} & \text{if } V_t < T_{exit} \\
  \text{State}_{t-1} & \text{if } T_{exit} \le V_t < T_{entry}
  \end{cases}$$

### 3.4 Conflict Resolution Precedence
When multiple adjustment sources match a target limit:
1. Hard / Mandate Constraints (Level 1)
2. Emergency Derisking Rules (Level 2)
3. Condition-Based Dynamic Adjustments (Level 3 - sorted by priority)
4. Time-Based Session Profile Adjustments (Level 4)
5. Approved Manual Overrides (Level 5)
6. Base Limit Configuration (Level 6)

---

## 4. Governance & Maker-Checker Flow

```
   [Trader / Risk Analyst] ─────────► [Request Manual Override]
                                               │
                                               ▼
                                      [Status: PENDING]
                                               │
               ┌───────────────────────────────┴───────────────────────────────┐
               ▼                                                               ▼
    [Self-Approval Attempt]                                         [Independent Checker Approval]
               │                                                               │
               ▼                                                               ▼
   ❌ 400 Maker-Checker Rejection                                   ✅ Status: APPROVED
                                                                               │
                                                                               ▼
                                                                  [Active during [From, To]]
                                                                               │
                                                                               ▼
                                                                  [Auto-Expiry or Explicit Revocation]
```

---

## 5. Storage & Persistence Model
- **`dynamic_limit_policies`**: Master policy record with active version pointer.
- **`dynamic_limit_policy_versions`**: Versioned rule sets with creator and approver tracking.
- **`dynamic_limit_conditions`**: Metrics, comparison operators, thresholds, hysteresis bands, and adjustment values.
- **`dynamic_limit_schedules`**: Exchange trading session profiles across IST and EST.
- **`dynamic_limit_overrides`**: Time-bounded manual overrides with maker-checker audit details.
- **`effective_limit_snapshots`**: Immutable point-in-time calculation outputs with full lineage JSON and SHA-256 hash.
- **`dynamic_limit_audit_events`**: Immutable audit log of all system transitions and approvals.

