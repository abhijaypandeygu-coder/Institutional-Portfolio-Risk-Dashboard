# M07.05 — Correlation Analysis API Reference

## 1. Overview
The **Correlation Analysis Engine** endpoints are mounted under:
- `/api/v1/market-risk/correlation` (Global pairwise, matrix, rolling, multi-horizon, and regime endpoints)
- `/api/v1/portfolios/{portfolio_id}/risk/correlation` (Portfolio-specific correlation matrix and rankings)

All calculations operate strictly on aligned returns, enforcing canonical asset ordering and providing complete statistical significance tests.

---

## 2. API Endpoints

### 2.1 Calculate Pairwise Correlation
**`POST /api/v1/market-risk/correlation/pairwise`**

Calculates the empirical return correlation between two assets over a configurable lookback window.

#### Request Body:
```json
{
  "asset_a_id": "INST_AAPL_01",
  "asset_b_id": "INST_MSFT_01",
  "lookback_days": 60,
  "as_of": "2026-02-04",
  "estimator": "PEARSON",
  "alignment_policy": "COMMON_SESSION_DATE",
  "missing_data_policy": "STRICT_PAIRWISE_COMPLETE",
  "portfolio_id": "PORT_TECH_01"
}
```

#### Response (200 OK):
```json
{
  "asset_a_id": "INST_AAPL_01",
  "asset_b_id": "INST_MSFT_01",
  "asset_a_symbol": "AAPL",
  "asset_b_symbol": "MSFT",
  "as_of_date": "2026-02-04T00:00:00Z",
  "lookback_days": 60,
  "estimator": "PEARSON",
  "correlation_coefficient": "0.784512",
  "sample_size": 42,
  "p_value": "0.000001",
  "t_statistic": "8.0124",
  "std_error": "0.061732",
  "ci_lower_95": "0.627845",
  "ci_upper_95": "0.880124",
  "covariance": "0.00018542",
  "volatility_a": "0.014231",
  "volatility_b": "0.016541",
  "alignment_applied": "COMMON_SESSION_DATE",
  "missing_data_strategy": "STRICT_PAIRWISE_COMPLETE"
}
```

---

### 2.2 Generate Correlation Matrix with PSD Diagnostics
**`POST /api/v1/market-risk/correlation/matrix`**

Computes an $N \times N$ correlation matrix across portfolio constituents or a custom universe. Includes full Positive Semi-Definite (PSD) eigenvalue diagnostics and optional non-destructive repair.

#### Request Body:
```json
{
  "portfolio_id": "PORT_TECH_01",
  "lookback_days": 60,
  "as_of": "2026-02-04",
  "estimator": "PEARSON",
  "repair_psd": true,
  "transformation_method": "EIGENVALUE_CLIPPING"
}
```

#### Response (200 OK):
```json
{
  "matrix_id": "180b6f98-...",
  "matrix_code": "CORR_MAT_790F32AA9A12",
  "portfolio_id": "PORT_TECH_01",
  "as_of_date": "2026-02-04T00:00:00Z",
  "lookback_days": 60,
  "estimator": "PEARSON",
  "dimension": 3,
  "asset_ids": ["INST_AAPL_01", "INST_GOOGL_01", "INST_MSFT_01"],
  "asset_symbols": ["AAPL", "GOOGL", "MSFT"],
  "matrix": [
    ["1.000000", "0.654210", "0.784512"],
    ["0.654210", "1.000000", "0.589120"],
    ["0.784512", "0.589120", "1.000000"]
  ],
  "psd_status": "VALID_PSD",
  "min_eigenvalue": "0.284512",
  "max_eigenvalue": "2.389104",
  "condition_number": "8.3972",
  "negative_eigenvalues_count": 0,
  "completeness_ratio": "1.0000",
  "average_correlation": "0.675947",
  "median_correlation": "0.654210",
  "transformed_matrix": null,
  "transformation_info": null
}
```

---

### 2.3 Compute Rolling Correlation Series
**`POST /api/v1/market-risk/correlation/rolling`**

Calculates moving-window correlation time series, tracking window-to-window changes ($\Delta \rho_t$) and baseline deviations.

#### Request Body:
```json
{
  "asset_a_id": "INST_AAPL_01",
  "asset_b_id": "INST_MSFT_01",
  "window_days": 20,
  "history_lookback_days": 180,
  "as_of": "2026-02-04",
  "estimator": "PEARSON"
}
```

#### Response (200 OK):
```json
{
  "asset_a_id": "INST_AAPL_01",
  "asset_b_id": "INST_MSFT_01",
  "asset_a_symbol": "AAPL",
  "asset_b_symbol": "MSFT",
  "window_days": 20,
  "history_lookback_days": 180,
  "estimator": "PEARSON",
  "baseline_correlation": "0.745210",
  "series": [
    {
      "observation_date": "2026-01-20",
      "correlation": "0.712450",
      "delta_rho": null,
      "baseline_deviation": "-0.032760",
      "sample_size": 20
    },
    {
      "observation_date": "2026-01-21",
      "correlation": "0.735100",
      "delta_rho": "0.022650",
      "baseline_deviation": "-0.010110",
      "sample_size": 20
    }
  ]
}
```

---

### 2.4 Multi-Horizon Lookback Comparison
**`GET /api/v1/market-risk/correlation/multi-horizon?asset_a_id={id1}&asset_b_id={id2}&as_of={date}`**

Compares co-movement across 20-day, 60-day, 120-day, and 252-day observation horizons.

#### Response (200 OK):
```json
{
  "asset_a_id": "INST_AAPL_01",
  "asset_b_id": "INST_MSFT_01",
  "asset_a_symbol": "AAPL",
  "asset_b_symbol": "MSFT",
  "as_of_date": "2026-02-04T00:00:00Z",
  "horizons": {
    "20D": "0.812400",
    "60D": "0.784512",
    "120D": "0.712500",
    "252D": "0.684000"
  }
}
```

---

### 2.5 Portfolio Correlation Rankings
**`GET /api/v1/portfolios/{portfolio_id}/risk/correlation/rankings?lookback_days=60&top_n=5`**

Returns ranked holding pairs for a portfolio:
- `top_positive_correlations`: Highest co-movement pairs (concentration risk).
- `top_negative_correlations`: Strongest negative pairs (hedging and diversification benefit).
- `most_stable_correlations`: Near-zero orthogonal pairs.

