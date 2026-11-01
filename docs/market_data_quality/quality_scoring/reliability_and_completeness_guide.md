# M03.07 Reliability and Completeness Guide

## 1. Reliability Scoring Mathematics
Feed reliability evaluates the infrastructural and transmission performance over specified rolling evaluation windows $W \in \{1\text{h}, 6\text{h}, 24\text{h}, 7\text{d}, 30\text{d}\}$.

### Availability Score ($S_{\text{avail}}$)
$$S_{\text{avail}} = \max\left(0, \min\left(100, \frac{T_{\text{eligible}} - T_{\text{outage}}}{T_{\text{eligible}}} \times 100\right)\right)$$
- If no eligible operating window is scheduled ($T_{\text{eligible}} = 0$), $S_{\text{avail}} = 100$.

### Timeliness Score ($S_{\text{time}}$)
$$S_{\text{time}} = \max\left(0, \min\left(100, \frac{N_{\text{timely}}}{N_{\text{expected}}} \times 100\right)\right)$$
- Observations arriving within SLA thresholds are counted as timely.

### Error Rate Score ($S_{\text{err}}$)
$$E_{\text{rate}} = \frac{N_{\text{failed}}}{N_{\text{ops}}} \times 100$$
$$S_{\text{err}} = \max(0, 100 - E_{\text{rate}})$$

### Feed Reliability Index
$$S_{\text{rel}} = w_{\text{avail}} S_{\text{avail}} + w_{\text{time}} S_{\text{time}} + w_{\text{err}} S_{\text{err}}$$
Standard default weights are $w_{\text{avail}} = 0.40, w_{\text{time}} = 0.35, w_{\text{err}} = 0.25$.

---

## 2. Completeness Scoring Mathematics

### Record Completeness ($S_{\text{comp}}$)
$$S_{\text{comp}} = \max\left(0, \min\left(100, \frac{N_{\text{valid\_unique}}}{N_{\text{expected}}} \times 100\right)\right)$$
- Duplicate records, malformed messages, and invalid prints are strictly excluded from $N_{\text{valid\_unique}}$.

### Field-Level Completeness Ratio ($R_{\text{field}}$)
$$R_{\text{field}} = \frac{N_{\text{present\_fields}}}{N_{\text{required\_fields}}}$$
If mandatory fields are missing (e.g. `price`, `timestamp`, `symbol`), field completeness is marked as degraded.

---

## 3. Freshness Scoring Function

Given observation age $A_{\text{ms}}$, target SLA $T_{\text{ms}}$, and maximum SLA $M_{\text{ms}}$:
$$S_{\text{fresh}} = \begin{cases} 
100.00 & \text{if } A_{\text{ms}} \le T_{\text{ms}} \\
100.00 \times \left(1.0 - \frac{A_{\text{ms}} - T_{\text{ms}}}{M_{\text{ms}} - T_{\text{ms}}}\right) & \text{if } T_{\text{ms}} < A_{\text{ms}} < M_{\text{ms}} \\
0.00 & \text{if } A_{\text{ms}} \ge M_{\text{ms}}
\end{cases}$$

### Cadence & Market Closed Awareness
- **Historical EOD Bars:** For Alpha Vantage EOD bars or historical daily feeds, age is calculated relative to end-of-day settlement or publication schedule. Real-time intraday SLA degradation is not applied.
- **Market Closed / Holiday Periods:** Feeds are evaluated according to exchange market session schedules. No false staleness or completeness penalties are levied when the underlying exchange is closed.
