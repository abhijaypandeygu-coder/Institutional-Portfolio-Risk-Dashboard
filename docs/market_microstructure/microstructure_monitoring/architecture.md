# M09.09 Microstructure Monitoring Architecture

## 1. Overview & Objective

**M09.09 — Microstructure Monitoring** delivers high-frequency, institutional-grade surveillance and short-horizon anomaly detection within the Institutional Portfolio Risk Dashboard. It operates without modifying raw upstream books or executing orders, strictly serving as an analytical surveillance layer.

The module provides four primary capabilities:
1. **Spread Volatility & Widening:** Measures short-term spread instability, rolling sample standard deviation, CV, time-weighted mean, and robust standardized widening ($Z_{\text{robust}}$).
2. **Depth Fluctuations & Depletion:** Tracks additions, reductions, price-band depth shifts, rapid depletion velocity, and replenishment recovery ratios ($R_{\text{recovery}}$).
3. **Update Intensity & Burst Detection:** Quantifies incoming message rates vs. actual reconstructed book-update rates, evaluating burst ratios and statistical deviations.
4. **Staleness & Anomaly Lifecycle:** Distinguishes feed inactivity from book inactivity, monitors observation age and receive latency, and manages full lifecycle state machines (Detected $\rightarrow$ Active $\rightarrow$ Acknowledged $\rightarrow$ Recovering $\rightarrow$ Resolved).

---

## 2. Mathematical Formulations

### 2.1 Spread Volatility & Widening
- **Spread Change:** $\Delta S_t = S_t - S_{t-1}$
- **Percentage Change:** $\Delta S_{\%} = \frac{S_t - S_{t-1}}{S_{t-1}} \times 100$ (where $S_{t-1} > 0$)
- **Time-Weighted Mean:** $\overline{S}_{\text{TW}} = \frac{\sum_j S_j \Delta t_j}{\sum_j \Delta t_j}$
- **Robust Z-Score:** $Z_{\text{robust}} = \frac{S_t - \text{Median}(S)}{1.4826 \times \text{MAD}(S)}$

### 2.2 Depth Depletion & Replenishment
- **Depletion Velocity:** $\text{DepletionRate} = \frac{D_{t-1} - D_t}{\Delta t}$
- **Replenishment Recovery Ratio:**
  $$R_{\text{recovery}} = \frac{D_t - D_{\text{post}}}{D_{\text{base}} - D_{\text{post}}}$$

### 2.3 Update Intensity Separation
- **Message Rate:** $\lambda_{\text{msg}} = \frac{N_{\text{messages}}}{\Delta t}$
- **Book Change Rate:** $\lambda_{\text{book}} = \frac{N_{\text{book\_updates}}}{\Delta t}$
- **Intensity Ratio:** $\text{IntensityRatio} = \frac{\lambda_{\text{current}}}{\lambda_{\text{baseline}}}$

### 2.4 Feed Staleness
- **Observation Age:** $\text{Age} = t_{\text{now}} - t_{\text{source}}$
- **Receive Latency:** $\text{Latency} = t_{\text{recv}} - t_{\text{source}}$

---

## 3. Data Lineage & Database Architecture

M09.09 persists monitoring metrics and anomaly state machines across 13 dedicated tables:
- `microstructure_monitoring_configs`: Versioned rule definitions.
- `microstructure_spread_monitoring`: Short-horizon spread rolling analytics.
- `microstructure_depth_monitoring`: Displayed depth fluctuations and replenishment metrics.
- `microstructure_depth_events`: Granular event-level changes (explicit vs aggregate).
- `microstructure_update_intensity`: Message rate vs book change rates.
- `microstructure_feed_freshness`: Observation age and receive latency.
- `microstructure_anomaly_rules`: Deterministic evaluation rules.
- `microstructure_anomaly_models`: Statistical detector definitions (MAD, EWMA, CUSUM).
- `microstructure_anomaly_events`: Core anomaly state machine.
- `microstructure_anomaly_evidence`: Structured evidence and provenance references.
- `microstructure_anomaly_transitions`: State-transition audit log.
- `microstructure_anomaly_episodes`: Multi-anomaly clustering.
- `microstructure_monitoring_baselines`: Time-of-day reference distributions.

