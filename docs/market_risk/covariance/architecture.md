# M07.06 — Covariance Analysis Engine: Technical Architecture

## 1. Executive Summary & Purpose
The **M07.06 Covariance Analysis** module is an institutional-grade quantitative risk system that models the joint variability of asset returns and provides the foundational statistical input for portfolio risk models (e.g., portfolio variance, risk budgeting, factor models, and parametric VaR/Expected Shortfall).

### Core Capabilities:
1. **Never calculates covariance directly from price levels**; operates strictly on aligned return vectors ($R_t$).
2. **Multi-Estimator Suite:** Supports unbiased sample covariance ($n-1$ denominator), population covariance ($n$ denominator), and Exponentially Weighted Moving Average (EWMA) covariance.
3. **Portfolio Covariance & Risk Contributions:** Computes portfolio variance ($\sigma_p^2 = \mathbf{w}^T \Sigma \mathbf{w}$), portfolio volatility ($\sigma_p = \sqrt{\mathbf{w}^T \Sigma \mathbf{w}}$), Marginal Contributions to Variance ($MCV_i = (\Sigma \mathbf{w})_i$), Component Contributions to Variance ($CV_i = w_i (\Sigma \mathbf{w})_i$), Marginal Contributions to Volatility ($MCR_i = (\Sigma \mathbf{w})_i / \sigma_p$), and Component Contributions to Volatility ($CR_i = w_i (\Sigma \mathbf{w})_i / \sigma_p$).
4. **Cross-Portfolio Covariance:** Evaluates joint co-movement between two portfolios: $\operatorname{Cov}(R_A, R_B) = \mathbf{w}_A^T \Sigma \mathbf{w}_B$.
5. **Positive Semi-Definite (PSD) Diagnostics & Repair:** Eigenvalue decomposition via symmetric solver (`numpy.linalg.eigvalsh`), condition number diagnostics, symmetry checks, and non-destructive PSD matrix reconstruction ($\Sigma^* = D R^* D$).
6. **Rolling Covariance Dynamics:** Moving window covariance tracking with step-to-step changes ($\Delta \Sigma_{ij, t}$).

---

## 2. Architectural Boundaries & Data Flow

```mermaid
flowchart TD
    subgraph Data Sources
        M04_Master["M04 Instrument Master\n(Canonical Identifiers & Symbols)"]
        M04_Prices["M04.05 Price Reference\n(Official Closing Prices)"]
        M07_Vol["M07.01 Volatility Engine\n(Resolved Prices & Return Calculations)"]
        M05_Position["M05.02 Position Management\n(PositionBook Holdings & Weights)"]
    end

    subgraph Mathematical Engine
        ReturnAdapter["Return Series Resolution\n(Daily Log Returns via M07.01)"]
        PairwiseCov["Pairwise Covariance\n(Sample n-1, Population n, EWMA)"]
        MatrixEngine["N x N Matrix Construction\n(Symmetry, Variance Diagonal, PSD Diagnostics)"]
        PSDRepair["Covariance PSD Repair\n(Sigma* = D R* D via Higham/Clipping)"]
        PortfolioEngine["Portfolio Risk Engine\nw^T Sigma w, MCV, CV, MCR, CR"]
        CrossPortEngine["Cross-Portfolio Covariance\nw_A^T Sigma w_B"]
        RollingEngine["Rolling Covariance Series\n(Window Deltas)"]
    end

    subgraph Storage Layer
        T_Configs[("m07_covariance_configs")]
        T_Runs[("m07_covariance_calculation_runs")]
        T_Pairs[("m07_covariance_pair_results")]
        T_Matrices[("m07_covariance_matrices")]
        T_Trans[("m07_covariance_matrix_transformations")]
        T_PortResults[("m07_portfolio_covariance_results")]
    end

    subgraph API Layer
        API_Pairwise["POST /pairwise"]
        API_Matrix["POST /matrix"]
        API_Rolling["POST /rolling"]
        API_Portfolio["POST /portfolio"]
        API_PortPair["POST /portfolio-pair"]
    end

    M04_Prices --> ReturnAdapter
    M07_Vol --> ReturnAdapter
    M05_Position --> PortfolioEngine
    M04_Master --> PairwiseCov

    ReturnAdapter --> PairwiseCov
    PairwiseCov --> MatrixEngine
    MatrixEngine --> PSDRepair
    MatrixEngine --> PortfolioEngine
    MatrixEngine --> CrossPortEngine
    PairwiseCov --> RollingEngine

    PairwiseCov --> T_Pairs
    MatrixEngine --> T_Matrices
    PSDRepair --> T_Trans
    PortfolioEngine --> T_PortResults

    T_Pairs --> API_Pairwise
    T_Matrices --> API_Matrix
    RollingEngine --> API_Rolling
    PortfolioEngine --> API_Portfolio
    CrossPortEngine --> API_PortPair
```

---

## 3. Mathematical Specifications

### 3.1 Pairwise Estimators
Given aligned returns $X = \{r_{A, t}\}_{t=1}^n$ and $Y = \{r_{B, t}\}_{t=1}^n$:

1. **Sample Covariance ($n-1$ denominator):**
   $$\operatorname{Cov}(X, Y) = \frac{1}{n-1} \sum_{t=1}^n (x_t - \bar{x})(y_t - \bar{y})$$

2. **Population Covariance ($n$ denominator):**
   $$\operatorname{Cov}_{\text{pop}}(X, Y) = \frac{1}{n} \sum_{t=1}^n (x_t - \bar{x})(y_t - \bar{y})$$

3. **Relationship with Correlation and Volatilities:**
   $$\operatorname{Cov}(X, Y) = \rho_{XY} \sigma_X \sigma_Y$$

4. **Units:**
   Covariance is expressed in **decimal-return squared** ($R^2$).

### 3.2 Portfolio Variance & Risk Contributions
For asset weight vector $\mathbf{w}$ and covariance matrix $\Sigma$:

1. **Portfolio Variance:**
   $$\sigma_p^2 = \mathbf{w}^T \Sigma \mathbf{w} = \sum_{i=1}^N w_i^2 \Sigma_{ii} + 2 \sum_{i < j} w_i w_j \Sigma_{ij}$$

2. **Portfolio Volatility:**
   $$\sigma_p = \sqrt{\mathbf{w}^T \Sigma \mathbf{w}}$$

3. **Marginal Contribution to Variance ($MCV$):**
   $$MCV_i = (\Sigma \mathbf{w})_i$$

4. **Component Contribution to Variance ($CV$):**
   $$CV_i = w_i (\Sigma \mathbf{w})_i, \quad \sum_{i=1}^N CV_i = \sigma_p^2$$

5. **Marginal Contribution to Volatility ($MCR$):**
   $$MCR_i = \frac{(\Sigma \mathbf{w})_i}{\sigma_p}$$

6. **Component Contribution to Volatility ($CR$):**
   $$CR_i = w_i \frac{(\Sigma \mathbf{w})_i}{\sigma_p}, \quad \sum_{i=1}^N CR_i = \sigma_p$$

### 3.3 Positive Semi-Definite Matrix Regularization
When empirical covariance matrices fail PSD constraints ($\lambda_{\min} < -10^{-8}$):
1. Extract standard deviations $D = \operatorname{diag}(\sqrt{\Sigma_{ii}})$.
2. Compute correlation matrix $R = D^{-1} \Sigma D^{-1}$.
3. Regularize correlation matrix $R^*$ to the nearest PSD correlation matrix using spectral eigenvalue clipping or Higham alternating projections.
4. Reconstruct covariance matrix:
   $$\Sigma^* = D R^* D$$
Original empirical matrices are never mutated in-place; all transformed matrices are recorded in `m07_covariance_matrix_transformations`.
