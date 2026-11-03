# M08.08 — Factor Monitoring Architecture & Mathematical Specification

## 1. Overview and Core Purpose

**M08.08 Factor Monitoring** is the automated surveillance and factor control engine of the Institutional Portfolio Risk Dashboard. It operates downstream of factor exposure estimation (M08.02), factor sensitivity regressions (M08.03), and factor attribution / systematic risk (M08.04, M08.05). 

The module tracks portfolio factor risk profiles across time, quantifies exposure drift against previous snapshots and approved targets, calculates factor concentration (Herfindahl-Hirschman Index and effective number of factors), and enforces multi-level threshold policies through a state machine with hysteresis and persistence verification.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Upstream Factor Intelligence                         │
│   M08.01 Factor Definitions & Model Version Registries                 │
│   M08.02 Portfolio Factor Exposure Snapshots                           │
│   M08.04 Euler Risk Contributions & Factor Attribution                 │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   M08.08 Factor Monitoring Engine                      │
│                                                                        │
│  ┌────────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ Exposure Drift Engine  │  │ Factor Concentration Engine          │  │
│  │ • Absolute / Direction │  │ • Exposure-based HHI & N_eff         │  │
│  │ • Standardized Δβ/1σ   │  │ • Risk-based HHI & N_eff (Euler RC)  │  │
│  │ • Holdings vs Loadings │  │ • Top-1 / Top-2 / Top-3 Shares       │  │
│  │   Decomposition        │  │                                      │  │
│  └───────────┬────────────┘  └──────────────────┬───────────────────┘  │
│              │                                  │                      │
│              └─────────────────┬────────────────┘                      │
│                                │                                       │
│                                ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Threshold Surveillance & State Machine Engine                    │  │
│  │ • Headroom & Deterministic Utilization Rate                      │  │
│  │ • State Machine: NORMAL ↔ WARNING ↔ BREACH ↔ CRITICAL_BREACH     │  │
│  │ • Hysteresis Buffer & Consecutive Count Persistence Verification │  │
│  │ • Active Breach Retain Guardrail on Missing/Null Inputs          │  │
│  └─────────────────────────────┬────────────────────────────────────┘  │
│                                │                                       │
│                                ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Breach Lifecycle & Typed Event Dispatcher                        │  │
│  │ • Detection, Consecutive Counts, Acknowledgment, Recovery        │  │
│  │ • Deterministic Deduplication Keys for Downstream Alerting (M12) │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Mathematical Framework

### 2.1 Exposure Drift Monitoring

Given current exposure $\beta_{k,t}$ and reference exposure $\beta_{k,\text{ref}}$ (from previous snapshot $t-1$, historical baseline $T$, or approved target profile $\beta_k^*$):

1. **Signed Drift:**
   $$\Delta \beta_k = \beta_{k,t} - \beta_{k,\text{ref}}$$

2. **Absolute Drift:**
   $$|\Delta \beta_k| = |\beta_{k,t} - \beta_{k,\text{ref}}|$$

3. **Percentage Drift:**
   $$\% \Delta \beta_k = \begin{cases}
   \text{UNDEFINED (Guardrail)}, & \text{if } |\beta_{k,\text{ref}}| < 10^{-4} \\
   \frac{\beta_{k,t} - \beta_{k,\text{ref}}}{|\beta_{k,\text{ref}}|} \times 100, & \text{otherwise}
   \end{cases}$$

4. **Standardized Drift:**
   $$\Delta \beta_k^{1\sigma} = \frac{\beta_{k,t} - \beta_{k,\text{ref}}}{\sigma(\beta_k)}$$
   where $\sigma(\beta_k)$ is the rolling standard deviation of exposure over the historical window.

5. **Sign Reversal Detection:**
   $$\text{is\_sign\_reversal} = (\beta_{k,t} \cdot \beta_{k,\text{ref}} < 0) \land (|\beta_{k,t}| > 10^{-6}) \land (|\beta_{k,\text{ref}}| > 10^{-6})$$

### 2.2 Symmetric Holdings vs. Loadings Decomposition

Drift in portfolio exposure $\Delta \beta_k = \beta_{k,t} - \beta_{k,t-1}$ is decomposed across all holdings $\mathcal{U} = \mathcal{H}_t \cup \mathcal{H}_{t-1}$ into weight changes (manager trading) and loading changes (security sensitivity shifts):

$$\Delta(w_i \beta_{i,k}) = \underbrace{\Delta w_i \left( \frac{\beta_{i,k,t} + \beta_{i,k,t-1}}{2} \right)}_{\text{Holding Weight Effect}} + \underbrace{\Delta \beta_{i,k} \left( \frac{w_{i,t} + w_{i,t-1}}{2} \right)}_{\text{Factor Loading Effect}}$$

Where:
- New positions entering ($i \notin \mathcal{H}_{t-1}$): $w_{i,t-1} = 0, \beta_{i,k,t-1} = \beta_{i,k,t}$
- Positions exited ($i \notin \mathcal{H}_t$): $w_{i,t} = 0, \beta_{i,k,t} = \beta_{i,k,t-1}$
- Exact Additive Property:
  $$\sum_{i \in \mathcal{U}} \text{weight\_effect}_i + \sum_{i \in \mathcal{U}} \text{loading\_effect}_i \equiv \Delta \beta_k$$

### 2.3 Factor Concentration Metrics

#### Exposure-Based Concentration
Standardized absolute exposure proportion for factor $k \in \{1, \dots, K\}$:
$$p_k^{\text{exp}} = \frac{|\beta_k|}{\sum_{j=1}^K |\beta_j|}$$

- **Exposure HHI:**
  $$\text{HHI}^{\text{exp}} = \sum_{k=1}^K (p_k^{\text{exp}})^2$$
- **Effective Number of Exposure Factors:**
  $$N_{\text{eff}}^{\text{exp}} = \frac{1}{\text{HHI}^{\text{exp}}}$$
- **Top-$N$ Exposure Dominance:**
  $$\text{Top1} = \max_k p_k^{\text{exp}}, \quad \text{Top2} = p_{(1)}^{\text{exp}} + p_{(2)}^{\text{exp}}, \quad \text{Top3} = \sum_{m=1}^{\min(3, K)} p_{(m)}^{\text{exp}}$$

#### Risk-Contribution-Based Concentration
Using Euler systematic risk contributions $RC_k = \beta_k \frac{(\Omega \boldsymbol{\beta})_k}{\sigma_{\text{sys}}}$ from M08.04:
$$p_k^{\text{risk}} = \frac{|RC_k|}{\sum_{j=1}^K |RC_j|}$$

- **Risk HHI:**
  $$\text{HHI}^{\text{risk}} = \sum_{k=1}^K (p_k^{\text{risk}})^2$$
- **Effective Number of Risk Factors:**
  $$N_{\text{eff}}^{\text{risk}} = \frac{1}{\text{HHI}^{\text{risk}}}$$

---

## 3. Threshold Engine & Breach State Machine

### 3.1 Metrics Monitored
- `ABSOLUTE_FACTOR_EXPOSURE`: $|\beta_k|$
- `DIRECTIONAL_FACTOR_EXPOSURE`: $\beta_k$
- `TARGET_DEVIATION`: $|\beta_k - \beta_k^*|$
- `FACTOR_CONCENTRATION_HHI`: $\text{HHI}^{\text{exp}}$ or $\text{HHI}^{\text{risk}}$
- `SYSTEMATIC_RISK_RATIO`: $\frac{\sigma_{\text{sys}}}{\sigma_{\text{total}}}$

### 3.2 Utilization and Headroom
For ceiling policies:
$$\text{utilization\_pct} = \frac{\text{current\_value}}{\text{breach\_threshold}} \times 100$$
$$\text{headroom} = \text{breach\_threshold} - \text{current\_value}$$

### 3.3 State Machine and Hysteresis
States: `NORMAL`, `WARNING`, `BREACH`, `CRITICAL_BREACH`, `PENDING_CONFIRMATION`, `RECOVERY_PENDING`, `RECOVERED`.

- **Breach Persistence:** An evaluation enters `BREACH` only when consecutive violations $\ge P_{\text{breach}}$.
- **Recovery Hysteresis:** An active breach remains in `BREACH` unless the value drops below $\text{threshold}_{\text{recovery}} < \text{threshold}_{\text{breach}}$.
- **Recovery Persistence:** Once below recovery threshold, status transitions to `RECOVERY_PENDING` until consecutive recoveries $\ge R_{\text{recovery}}$, upon which it transitions to `RECOVERED`.
- **Missing Data Guardrail:** If `current_value` is `None` / unavailable, an active breach **must never clear**; it is retained as active with `EVALUATION_ERROR`.

---

## 4. Database Schema Structure

M08.08 defines 10 relational tables:
1. `m08_08_monitoring_configs`: Target profiles and cadence configurations.
2. `m08_08_exposure_targets`: Approved factor exposure profiles.
3. `m08_08_exposure_target_components`: Component target levels and tolerances per factor.
4. `m08_08_threshold_policies`: Limit definitions with severity, warning, breach, and critical limits.
5. `m08_08_monitoring_runs`: Execution runs with SHA-256 cryptographic result signatures.
6. `m08_08_exposure_drift_results`: Granular drift measurements against reference benchmarks.
7. `m08_08_concentration_results`: Exposure and risk contribution HHI, $N_{\text{eff}}$, and Top-N shares.
8. `m08_08_threshold_evaluations`: Evaluated threshold results, headroom, and utilization rates.
9. `m08_08_breaches`: Persistent breach lifecycle entity tracking acknowledgment and recovery.
10. `m08_08_monitoring_events`: Auditable events with deterministic deduplication keys.

