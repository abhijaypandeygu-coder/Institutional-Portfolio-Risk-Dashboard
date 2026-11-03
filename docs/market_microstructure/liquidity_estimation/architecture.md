# M09.03 — Liquidity Estimation Architecture & Methodology

## 1. Executive Overview

**M09.03 — Liquidity Estimation** is an institutional-grade market microstructure module within the **Institutional Portfolio Risk Dashboard**. It estimates multi-dimensional equity liquidity characteristics by integrating:

1. **Traded Volume & Pace:** Actual executed trade volume ($V$) over discrete intervals, sessions, rolling ADV, median daily volume, and same-time-of-day intraday pace.
2. **Turnover & Pace:** Executed monetary value ($T = \sum P_j \cdot Q_j \cdot M$), ADTV, median daily turnover, and same-time-of-day pace, preserving native currencies.
3. **Transaction Friction:** Consumes validated relative bid-ask spreads (bps) directly from **M09.01**.
4. **Displayed Order Book Depth:** Consumes time-weighted top-N notional depth directly from **M09.02**.
5. **Data Availability Scoring:** Measures valid observation duration across spread, depth, and trade feeds to evaluate measurement confidence.
6. **Composite Liquidity Scoring:** Normalized 0–100 composite score combining the four dimensions with hard coverage eligibility gates.
7. **Liquidity Bucketing & Transition Tracking:** Classifies instruments into discrete categories (`VERY_HIGH_LIQUIDITY` down to `VERY_LOW_LIQUIDITY` and `INSUFFICIENT_DATA`), logging historical transitions.

---

## 2. Mathematical & Statistical Formulations

### 2.1 Traded Volume & Turnover Aggregation
For an interval $[t_0, t_1]$ containing $n$ eligible executions:
$$V_{[t_0, t_1]} = \sum_{j=1}^{n} Q_j$$
$$T_{[t_0, t_1]} = \sum_{j=1}^{n} P_j \cdot Q_j \cdot M$$
Where $M$ is the contract multiplier (default 1.0 for equities). Canceled trades are excluded, and duplicate event IDs are filtered out.

### 2.2 Rolling Statistics & Intraday Pace
For $N$ eligible completed trading sessions:
$$\text{ADV}_N = \frac{1}{N}\sum_{d=1}^{N} V_d, \quad \text{ADTV}_N = \frac{1}{N}\sum_{d=1}^{N} T_d$$
$$\text{MDV}_N = \text{Median}(V_1, \dots, V_N), \quad \text{MDTV}_N = \text{Median}(T_1, \dots, T_N)$$
$$CV_V = \frac{\sigma_V}{\overline{V}}, \quad CV_T = \frac{\sigma_T}{\overline{T}}$$
Intraday pace relative to historical same-time median:
$$VP_t(\tau) = \frac{V_{\text{current}, t}(\tau)}{\text{Median}(V_{\text{historical}, d}(\tau))}, \quad TP_t(\tau) = \frac{T_{\text{current}, t}(\tau)}{\text{Median}(T_{\text{historical}, d}(\tau))}$$

### 2.3 Component Normalization & Subscores
Within a compatible peer group $G$:
- **Percentile Rank $PR(x_i)$:**
  $$PR(x_i) = \frac{\sum \mathbf{1}_{x < x_i} + 0.5 \sum \mathbf{1}_{x = x_i}}{N} \times 100$$
- **Spread Subscore (lower spread is better):**
  $$S_{\text{spread}} = 100 \times (1 - PR(\text{Spread}_{\text{bps}}))$$
- **Depth Subscore (greater depth is better):**
  $$S_{\text{depth}} = PR(\text{Depth}_{\text{notional}})$$
- **Turnover Subscore (greater turnover is better):**
  $$S_{\text{turnover}} = PR(\text{Turnover})$$

### 2.4 Data Availability Score
$$S_{\text{availability}} = 100 \times (\alpha C_{\text{spread}} + \beta C_{\text{depth}} + \gamma C_{\text{turnover}})$$
Where $\alpha + \beta + \gamma = 1.0$ (defaults: 0.33, 0.33, 0.34).

### 2.5 Composite Liquidity Score
$$L = w_s S_{\text{spread}} + w_d S_{\text{depth}} + w_t S_{\text{turnover}} + w_a S_{\text{availability}}$$
Subject to $\sum w_i = 1.0$ (defaults: 25% spread, 30% depth, 30% turnover, 15% availability).

*Hard Coverage Gate:* If any required component has coverage below the threshold (e.g. 50%), the composite score is returned as `None` with status `INSUFFICIENT_DATA`. Weights are never silently redistributed.

### 2.6 Liquidity Bucket Classification
| Score Range | Bucket Name | Rank |
| :--- | :--- | :---: |
| 80.0 – 100.0 | `VERY_HIGH_LIQUIDITY` | 1 |
| 60.0 – <80.0 | `HIGH_LIQUIDITY` | 2 |
| 40.0 – <60.0 | `MODERATE_LIQUIDITY` | 3 |
| 20.0 – <40.0 | `LOW_LIQUIDITY` | 4 |
| 0.0 – <20.0 | `VERY_LOW_LIQUIDITY` | 5 |
| Missing / Insufficient | `INSUFFICIENT_DATA` | 6 |

---

## 3. Relational Database Schema

The module implements 9 tables:
- `m09_03_liquidity_metric_configs`: Versioned volume/turnover calculation parameters.
- `m09_03_liquidity_volume_aggregates`: Executed volume over discrete time intervals.
- `m09_03_liquidity_turnover_aggregates`: Executed trade value over discrete intervals with currency metadata.
- `m09_03_liquidity_rolling_statistics`: Rolling ADV, ADTV, CV, stddev, percentiles, and pace metrics.
- `m09_03_liquidity_score_configs`: Scoring weights, normalization bounds, and minimum coverage gates.
- `m09_03_liquidity_score_snapshots`: Point-in-time composite scores, component subscores, and contributions.
- `m09_03_liquidity_bucket_policies`: Versioned bucket classification threshold definitions.
- `m09_03_liquidity_bucket_snapshots`: Point-in-time bucket classifications.
- `m09_03_liquidity_bucket_transitions`: Event log of transitions between liquidity categories.

