# M07.04 — Drawdown Analytics Architecture

## 1. Executive Summary

Module `M07.04 — Drawdown Analytics` delivers an institutional drawdown and recovery analytics engine for the Institutional Portfolio Risk Dashboard. The system measures losses from historical peaks, calculates current distance to the running high-water mark, identifies individual drawdown episodes, and computes recovery and underwater durations.

Core capabilities implemented:
1. **Running High-Water Mark (HWM)**: Evaluates peak values $HWM_t = \max(V_0, \dots, V_t)$ without lookahead bias.
2. **Current Drawdown**: Measures distance from latest value to high-water mark, tracking days since peak and recovery status.
3. **Maximum Drawdown (MDD)**: Identifies the largest peak-to-trough decline across configurable lookback periods.
4. **Drawdown Episode Detection**: Linear-pass segmentation tracking peak, trough, recovery, partial recoveries, and right-censored ongoing episodes.
5. **Recovery & Underwater Durations**: Measures peak-to-trough, trough-to-recovery, and total underwater durations in calendar days and session counts.
6. **Lookback Window Comparisons**: Side-by-side analysis across 1M, 3M, 6M, 1Y, and Since Inception.

---

## 2. Core Mathematical Specifications

### 2.1 Running High-Water Mark & Drawdown Formulas
For an authoritative value series $V_0, V_1, \dots, V_t$:
- **Running High-Water Mark**:
  $$HWM_t = \max(V_0, V_1, \dots, V_t)$$
- **Signed Percentage Drawdown**:
  $$D_t = \frac{V_t}{HWM_t} - 1 \le 0$$
- **Positive Drawdown Magnitude**:
  $$DD_t = 1 - \frac{V_t}{HWM_t} \ge 0$$
  $$DD_t^{\%} = DD_t \times 100\%$$
- **Absolute Drawdown Amount**:
  $$DD_t^{\text{Amount}} = HWM_t - V_t$$

### 2.2 Episode Segmentation & Recovery Condition
- **Episode Start**: When $DD_t > \text{tolerance}$, initiated at peak timestamp $T_{\text{Peak}}$ with value $P = HWM_t$.
- **Trough Update**: If $V_t < V_{\text{Trough}}$, updates trough value and timestamp.
- **Partial Recovery**: When $V_t > V_{\text{Trough}}$ but $V_t < P$, the episode remains `ONGOING`.
- **Full Recovery**: First eligible observation where $V_t \ge P$. Episode closes with status `RECOVERED`.
- **Right-Censored Episodes**: If $V_T < P$ at the analysis endpoint, episode is marked `ONGOING` with no fabricated recovery date.

### 2.3 Durations
- Peak-to-Trough: $T_{\text{Trough}} - T_{\text{Peak}}$
- Trough-to-Recovery: $T_{\text{Recovery}} - T_{\text{Trough}}$
- Total Underwater: $T_{\text{Recovery}} - T_{\text{Peak}}$ (or $T_{\text{AsOf}} - T_{\text{Peak}}$ if ongoing)

---

## 3. Database Schema

- `m07_drawdown_configs`: Policy settings for scope, price adjustment, and recovery tolerance.
- `m07_drawdown_series_results`: Time series of values, running high-water mark, signed & positive drawdown.
- `m07_drawdown_episodes`: Discrete episode records storing peak, trough, recovery, durations, and status.
- `m07_maximum_drawdown_results`: Authoritative peak-to-trough declines across lookback windows.
- `m07_drawdown_recovery_stats`: Aggregate statistics (average, median, longest recovery and underwater durations).
- `m07_drawdown_diagnostics`: Audit logs for data freshness, gaps, and series continuity.

---

## 4. API Endpoints

Mounted under `/api/v1/market-risk/drawdown`, `/api/v1/portfolios/{portfolio_id}/risk/drawdown`, and `/api/v1/portfolio-groups/{group_id}/risk/drawdown`:
- `GET /current`: Current drawdown percentage, amount, status, and days since peak.
- `GET /maximum`: Maximum drawdown percentage, amount, peak, trough, and recovery dates.
- `GET /episodes`: Ranked list of drawdown episodes with pagination.
- `GET /history`: Time series of values, running peaks, and drawdown percentages.
- `GET /recovery-statistics`: Summary statistics across completed and ongoing episodes.
- `GET /comparison`: Multi-horizon comparison (1M, 3M, 6M, 1Y, Since Inception).
- `GET /portfolios/{id}/risk/drawdown`: Executive summary dashboard for a portfolio.

