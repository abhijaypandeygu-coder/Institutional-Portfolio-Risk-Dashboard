# M07.10 Risk Forecasting Module Architecture

## 1. Executive Overview

The **M07.10 Risk Forecasting** module delivers an institutional-grade forward-looking risk analytics engine within the **Institutional Portfolio Risk Dashboard**. The module estimates future asset and portfolio volatility over configurable trading horizons ($h = 1, 2, \dots, H$) using three core forecasting methodologies:
1. **Rolling Historical Variance:** Unconditional baseline utilizing trailing estimation windows.
2. **Exponentially Weighted Moving Average (EWMA):** Recursive dynamic variance modeling with configurable decay factor $\lambda$ (RiskMetrics convention $\lambda = 0.94$).
3. **GARCH(1,1):** Conditional heteroskedastic maximum likelihood estimation with strict stationarity constraints ($\alpha + \beta < 1$) and multi-step mean reversion toward long-run variance ($V_L = \frac{\omega}{1 - \alpha - \beta}$).

---

## 2. Mathematical Formulations

### 2.1 Rolling Historical Variance Baseline
For lookback window $W$:
$$\bar{r}_t = \frac{1}{W} \sum_{j=0}^{W-1} r_{t-j}$$
$$\hat{h}_{t+1|t} = \frac{1}{W-1} \sum_{j=0}^{W-1} (r_{t-j} - \bar{r}_t)^2$$
For horizon $H$, cumulative variance:
$$H_{t, H|t} = H \cdot \hat{h}_{t+1|t}, \quad \sigma_{t, H|t} = \sqrt{H_{t, H|t}}$$

### 2.2 EWMA Conditional Variance
Recursive update from prior conditional variance:
$$\hat{h}_{t+1|t} = \lambda \hat{h}_{t|t-1} + (1 - \lambda) \epsilon_t^2$$
Multi-step variance assumption under martingale difference property of innovations:
$$\hat{h}_{t+k|t} = \hat{h}_{t+1|t} \quad \forall k \ge 1$$

### 2.3 GARCH(1,1) Specification
$$r_t = \mu + \epsilon_t, \quad \epsilon_t = \sigma_t z_t, \quad z_t \sim \mathcal{N}(0, 1)$$
$$\sigma_t^2 = \omega + \alpha \epsilon_{t-1}^2 + \beta \sigma_{t-1}^2$$
Constraints: $\omega > 0, \alpha \ge 0, \beta \ge 0, \alpha + \beta < 1$.
Long-run unconditional variance:
$$V_L = \frac{\omega}{1 - \alpha - \beta}$$
Multi-step conditional variance forecast recursion:
$$\hat{h}_{t+k|t} = V_L + (\alpha + \beta)^{k-1} (\hat{h}_{t+1|t} - V_L)$$

### 2.4 Forecast Evaluation & QLIKE Loss
Given forecast variance $\hat{h}_t$ and realized proxy $RV_t$:
- Forecast error: $e_t = \hat{\sigma}_t - \sigma_t^{\text{realized}}$
- Mean Absolute Error (MAE): $\frac{1}{N} \sum |e_t|$
- Root Mean Squared Error (RMSE): $\sqrt{\frac{1}{N} \sum e_t^2}$
- Quasi-Likelihood (QLIKE) loss:
  $$\text{QLIKE}_t = \frac{RV_t}{\hat{h}_t} - \ln\left(\frac{RV_t}{\hat{h}_t}\right) - 1$$
- Calibration regression:
  $$RV_t = a + b \hat{h}_t + u_t \quad (\text{ideal: } a=0, b=1)$$

---

## 3. Database Schema

- `m07_10_forecast_configurations`: Versioned parameter sets and model settings.
- `m07_10_forecast_runs`: Calculation execution header storing 1-step and cumulative horizon metrics, parameters, and line of sight.
- `m07_10_volatility_forecast_steps`: Step-by-step path records for multi-step horizons ($k = 1, \dots, H$).
- `m07_10_forecast_evaluations`: Ex-post evaluation records matching forecasts with subsequent realized proxies.
- `m07_10_model_comparisons`: Side-by-side performance records across competing models.
- `m07_10_monitoring_events`: Auditable alert records for persistent underforecasting or calibration drift.
