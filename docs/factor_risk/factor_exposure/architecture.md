# M08.02 — Factor Exposure: Architecture & Econometric Guide

## 1. Executive Overview

**M08.02 — Factor Exposure** is the quantitative sensitivity and attribution engine within **M08 — Factor & Systematic Risk Analytics** in the **Institutional Portfolio Risk Dashboard**.

M08.02 answers the fundamental risk question:
> *How sensitive are individual portfolio holdings and aggregate portfolios to systematic factor movements, and how have those sensitivities evolved over time due to security return dynamics versus portfolio rebalancing?*

The module operates as a strictly governed, quantitative statistical engine:
- Estimating security-level factor sensitivities ($\beta_{i,k}$) via multi-factor time-series regressions.
- Aggregating individual loadings into signed portfolio factor exposures ($\beta_{p,k}$) using authoritative NAV weights.
- Standardizing exposures (1-sigma factor volatility scaling and cross-sectional z-scores).
- Decomposing historical exposure changes into weight-driven versus loading-driven effects.

---

## 2. Mathematical & Econometric Specification

### 2.1 Multi-Factor Time-Series Regression

For security $i$ over an estimation window of $T$ observations against an approved factor model containing $K$ factors:

$$R_{i,t} - R_{f,t} = \alpha_i + \sum_{k=1}^K \beta_{i,k} F_{k,t} + \epsilon_{i,t}$$

In matrix form:
$$\mathbf{y}_i = \mathbf{X} \boldsymbol{\beta}_i + \boldsymbol{\epsilon}_i$$

Where:
- $\mathbf{y}_i \in \mathbb{R}^{T \times 1}$: Excess or total return vector of instrument $i$.
- $\mathbf{X} \in \mathbb{R}^{T \times P}$: Design matrix containing an intercept column $\mathbf{1}$ (if $include\_intercept = True$) and $K$ factor return columns in pinned model order ($P = K + 1$ or $K$).
- $\boldsymbol{\beta}_i \in \mathbb{R}^{P \times 1}$: Vector of regression parameters $[\alpha_i, \beta_{i,1}, \dots, \beta_{i,K}]^T$.

### 2.2 Numerical Solver (QR Decomposition)

Rather than computing unstable direct inverses $(X^T X)^{-1}$, M08.02 uses thin QR decomposition:
$$\mathbf{X} = \mathbf{Q} \mathbf{R}$$
$$\mathbf{R} \boldsymbol{\beta}_i = \mathbf{Q}^T \mathbf{y}_i$$

Solving by back-substitution provides maximal numerical precision even under near-collinear specifications.

### 2.3 Estimation Methods

1. **Rolling OLS (Default):** Fixed lookback window (e.g. 252 or 60 daily observations).
2. **Expanding OLS:** Expands from an initial start date through subsequent trading sessions.
3. **Exponentially Weighted Least Squares (EWLS):**
   Weighting observation $j \in \{0, \dots, T-1\}$ with decay factor $\lambda \in (0, 1)$ (default $\lambda = 0.94$):
   $$w_j = \lambda^{T - 1 - j}$$
   Solving $\mathbf{X}_w = \mathbf{W}^{1/2} \mathbf{X}$ and $\mathbf{y}_w = \mathbf{W}^{1/2} \mathbf{y}$.

### 2.4 Statistical Inference & Robust Standard Errors

- **HC3 Heteroskedasticity-Consistent Covariance:**
  $$\mathbf{V}_{HC3} = (\mathbf{X}^T \mathbf{X})^{-1} \left( \sum_{t=1}^T \frac{e_t^2}{(1 - h_t)^2} \mathbf{x}_t \mathbf{x}_t^T \right) (\mathbf{X}^T \mathbf{X})^{-1}$$
  where $h_t = \sum_j Q_{t,j}^2$ is the leverage value.
- **HAC Newey-West Standard Errors:** Adjusts for autocorrelation with Bartlett kernel bandwidth $L = \lfloor 4(T/100)^{2/9} \rfloor$.
- **Diagnostics:** $R^2$, Adjusted $R^2$, Condition Number, and Variance Inflation Factor (VIF).

---

## 3. Portfolio-Level Factor Exposure Aggregation

Portfolio factor exposure is computed using authoritative, signed NAV weights:

$$\beta_{p,k} = \sum_{i=1}^N w_i \beta_{i,k}$$

Where:
$$w_i = \frac{MV_i}{NAV_p}$$

- **Long positions:** $MV_i > 0 \implies w_i > 0$, positive factor sensitivity.
- **Short positions:** $MV_i < 0 \implies w_i < 0$, negative factor sensitivity (shorting a positive-beta asset hedges or creates a negative factor tilt).
- **Gross-Normalized Exposure (Analytical View):**
  $$w_i^{gross} = \frac{MV_i}{\sum_j |MV_j|}, \quad \beta_{p,k}^{gross} = \sum_{i=1}^N w_i^{gross} \beta_{i,k}$$

### Coverage Metric

$$\text{Coverage}_k = \frac{\sum_{i \in \text{Covered}_k} |w_i|}{\sum_{j \in \text{All}} |w_j|} \times 100\%$$

Incomplete coverage is never silently normalized to 100%; missing securities are flagged explicitly.

---

## 4. Exposure Normalization

1. **1-Sigma Standardized Loading:**
   $$\beta_{i,k}^{1\sigma} = \beta_{i,k} \cdot \sigma(F_k)$$
   Measures expected security return impact per 1-standard-deviation move in systematic factor $k$.
2. **Cross-Sectional Z-Score:**
   $$Z_{i,k} = \frac{\beta_{i,k} - \mu_k^{\text{universe}}}{\sigma_k^{\text{universe}}}$$

---

## 5. Symmetric Exact Exposure Change Decomposition

When portfolio exposure changes from $t-1$ to $t$:
$$\Delta \beta_{p,k} = \beta_{p,k,t} - \beta_{p,k,t-1}$$

For continuous holdings present at both dates, M08.02 evaluates the exact symmetric decomposition:

$$\Delta (w_i \beta_{i,k}) = \underbrace{\Delta w_i \left( \frac{\beta_{i,k,t} + \beta_{i,k,t-1}}{2} \right)}_{\text{Weight Effect}} + \underbrace{\Delta \beta_{i,k} \left( \frac{w_{i,t} + w_{i,t-1}}{2} \right)}_{\text{Loading Effect}}$$

For new entries: $\text{Effect} = w_{i,t} \beta_{i,k,t}$.
For exits: $\text{Effect} = - w_{i,t-1} \beta_{i,k,t-1}$.

$$\text{Total Change} \equiv \text{Weight Effect} + \text{Loading Effect} + \text{Entry/Exit Effect}$$
Reconciles to observed delta with zero mathematical residual.
