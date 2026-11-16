# M11.06 — Breach Detection: System Architecture

## 1. Overview and Purpose

The **Breach Detection (M11.06)** module is an institutional-grade component of the **Risk Limits & Control Framework (M11)** within the Institutional Portfolio Risk Dashboard.

Its primary responsibility is to continuously or periodically evaluate current portfolio risk metrics against applicable active boundaries (base limits from M11.01/M11.04, dynamic effective snapshots from M11.05) and determine threshold violations with mathematical rigor.

### Key Capabilities
1. **Active Limit Resolution:** Resolves applicable base and dynamic limits for evaluated portfolios, positions, sectors, and issuers.
2. **Warning & Hard-Limit Discrimination:** Separates warning alerts ($T_w$) from binding hard breaches ($T_h$) without conflation.
3. **Data Quality & Freshness Enforcement:** Validates metric age against configurable maximum thresholds and rejects stale or corrupted inputs (preventing false "within limit" classifications).
4. **Stateful Episode Tracking & Deduplication:** Groups repeated violating observations under a single persistent `BreachEpisode`, avoiding noisy duplicate incident creation.
5. **Persistence & Recovery Models:** Supports duration-based, consecutive observation, and window-based persistence, alongside hysteresis bands for recovery confirmation.
6. **Immutable Cryptographic Evidence:** Produces tamper-evident, timestamped `BreachEvent` records with exact metric, threshold, and effective snapshot references.

---

## 2. Component Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                   M11.06 BREACH DETECTION ENGINE                       │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌───────────────────────┐         ┌────────────────────────┐          │
│  │ Upstream Risk Metrics │         │ Active Limits & M11.05 │          │
│  │ (M06 Exposures, M07   │         │ Effective Limit        │          │
│  │  VaR/Vol, M09 Depth)  │         │ Snapshots              │          │
│  └───────────┬───────────┘         └───────────┬────────────┘          │
│              │                                 │                       │
│              ▼                                 ▼                       │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │           Input Quality & Freshness Assessment           │          │
│  │                                                          │          │
│  │   • M03 Data-Quality State Validation (CORRUPTED/INVALID)│          │
│  │   • Freshness Enforcement: Age = t_eval - t_metric       │          │
│  │   • Stale Input Rejection (Never defaults to Pass)       │          │
│  └───────────────────────────┬──────────────────────────────┘          │
│                              │                                         │
│                              ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │          Quantitative Boundary Comparison Engine         │          │
│  │                                                          │          │
│  │   • Utilization & Magnitude:                             │          │
│  │     - Max Cap: U = x / T, Magnitude = max(0, x - T)      │          │
│  │     - Min Floor: U = T / x, Magnitude = max(0, T - x)    │          │
│  │   • Severity Classification: LOW, MEDIUM, HIGH, CRITICAL │          │
│  └───────────────────────────┬──────────────────────────────┘          │
│                              │                                         │
│                              ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │          Episode Lifecycle & Persistence Tracker         │          │
│  │                                                          │          │
│  │   • Active Episode Resolution & Deduplication            │          │
│  │   • Observation Time-Series Logging                      │          │
│  │   • Persistence Modes (Duration, Consecutive, Window)    │          │
│  │   • Recovery Confirmation under Hysteresis               │          │
│  └───────────────────────────┬──────────────────────────────┘          │
│                              │                                         │
│                              ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │          Immutable Event Generation & Downstream Sync    │          │
│  │                                                          │          │
│  │   • Cryptographic Evidence & Full Lineage                │          │
│  │   • Publish to M11.08 Breach Monitoring & Escalation     │          │
│  │   • Expose Active Breach State to M11.07 Pre-Trade Risk  │          │
│  └──────────────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Mathematical Specifications

### 3.1 Maximum-Type Limits (Caps)
- **Utilization:**
  $$U = \frac{x}{T} \quad (T > 0)$$
- **Breach Condition:**
  $$\text{Violation} \iff x > T \quad (\text{or } x \ge T)$$
- **Breach Magnitude:**
  $$M = \max(0, x - T)$$
- **Excess Percentage:**
  $$\text{Excess}_{\%} = \frac{x - T}{|T|} \times 100$$

### 3.2 Minimum-Type Limits (Floors)
- **Utilization:**
  $$U = \frac{T}{x} \quad (x > 0)$$
- **Breach Condition:**
  $$\text{Violation} \iff x < T \quad (\text{or } x \le T)$$
- **Breach Magnitude:**
  $$M = \max(0, T - x)$$
- **Shortfall Percentage:**
  $$\text{Shortfall}_{\%} = \frac{T - x}{|T|} \times 100$$

### 3.3 Persistence Criteria
- **Duration-Based Persistence:**
  $$t_{\text{current}} - t_{\text{first violation}} \ge D_{\text{required}}$$
- **Consecutive Observation Persistence:**
  $$\text{Consecutive Violations} \ge N_{\text{required}}$$
- **Immediate Policy:**
  $$\text{Immediate Breach} \implies \text{Persistence Confirmed at } t_0$$

### 3.4 Recovery Hysteresis
To prevent chattering around a boundary:
$$\text{Recovered} \iff x \le T_{\text{recovery}} \quad (\text{where } T_{\text{recovery}} \le T_{\text{hard}} \text{ for caps})$$

---

## 4. Database Schema Structure
- **`breach_evaluations`**: Point-in-time record of every metric-to-limit comparison.
- **`breach_episodes`**: Stateful parent entity grouping recurring observations during an ongoing violation.
- **`breach_observations`**: Time-series log of all individual evaluations inside an episode.
- **`breach_events`**: Immutable structured breach events (`WARNING_ENTERED`, `HARD_BREACH_ENTERED`, `PERSISTENT_BREACH`, `BREACH_RECOVERED`).
- **`breach_detection_rules`**: Version-controlled rules defining persistence modes, windows, and hysteresis.
- **`breach_detection_rule_versions`**: Historical snapshots of detection rules.
- **`breach_event_links`**: Graph relations between linked events (`RECOVERY_OF`, `REOPENING_OF`, `DUPLICATE_OF`).
- **`breach_audit_events`**: Immutable audit logs of administrative and detection lifecycle changes.
