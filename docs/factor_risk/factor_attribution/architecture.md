# M08.04 — Factor Attribution Architecture Documentation

## 1. Executive Summary & Purpose

**M08.04 — Factor Attribution** completes the risk and return decomposition capabilities of the **Factor & Systematic Risk Analytics (M08)** domain within the Institutional Portfolio Risk Dashboard.

The module answers four fundamental quantitative questions:
1. **Factor Return Contribution:** How much of the portfolio's realized return is attributable to each systematic factor over a given evaluation window?
2. **Systematic Factor Risk Attribution:** How much portfolio risk is associated with each factor, incorporating factor exposures, factor volatilities, and cross-factor correlations via mathematically exact Euler decompositions?
3. **Residual and Unexplained Risk:** What portion of return and risk stems from stock-specific idiosyncratic components ($\epsilon_{p,t}$), and what is the cross-covariance between systematic factor tilts and residual variation?
4. **Attribution Reconciliation:** Does the bottom-up sum of systematic, risk-free, alpha, and residual components exactly match the total observed portfolio return and modeled portfolio risk within rigorous institutional tolerances?

---

## 2. Mathematical Foundation

### 2.1 Single-Period Factor Return Attribution
For excess return models:
$$R_{p,t} - R_{f,t} = \alpha_{p,t} + \sum_{k=1}^K \beta_{p,k,t-1} F_{k,t} + \epsilon_{p,t}$$
Or equivalently for total return models:
$$R_{p,t} = R_{f,t} + \alpha_{p,t} + \sum_{k=1}^K C_{k,t} + \epsilon_{p,t}$$
Where the single-period contribution of factor $k$ is:
$$C_{k,t} = \beta_{p,k,t-1} \cdot F_{k,t}$$

### 2.2 Bottom-Up Portfolio Factor Contribution
When security-level exposures are known:
$$C_{p,k,t} = \sum_{i=1}^N w_{i,t-1} \cdot \beta_{i,k,t-1} \cdot F_{k,t}$$
Where long positions have $w_i > 0$ and short positions have $w_i < 0$.

### 2.3 Exact Carino Multi-Period Logarithmic Linking
Standard arithmetic summation of single-period contributions does not compound to cumulative geometrically linked returns:
$$R_p^{cum} = \prod_{t=1}^T (1 + R_{p,t}) - 1 \neq \sum_{t=1}^T R_{p,t}$$

M08.04 implements exact **Carino logarithmic linking**:
1. Single-period coefficient:
   $$k_t = \frac{\ln(1 + R_{p,t})}{R_{p,t}} \quad \text{with} \quad \lim_{R_{p,t} \to 0} k_t = 1.0$$
2. Cumulative period coefficient:
   $$k = \frac{\ln(1 + R_p^{cum})}{R_p^{cum}} \quad \text{with} \quad \lim_{R_p^{cum} \to 0} k = 1.0$$
3. Exact multi-period factor contribution:
   $$C_{k,cum} = \sum_{t=1}^T \left( C_{k,t} \cdot \frac{k_t}{k} \right)$$
This guarantees the exact mathematical identity:
$$\sum_{k=1}^K C_{k,cum} + \text{Alpha}_{cum} + R_{f,cum} + \epsilon_{cum} = R_p^{cum}$$

### 2.4 Systematic Factor Risk Attribution (Euler Decomposition)
Given the factor sensitivity vector $\boldsymbol{\beta}_p \in \mathbb{R}^K$ and factor covariance matrix $\boldsymbol{\Sigma}_F \in \mathbb{R}^{K \times K}$:

- **Systematic Portfolio Variance:**
  $$\sigma_{sys}^2 = \boldsymbol{\beta}_p^T \boldsymbol{\Sigma}_F \boldsymbol{\beta}_p$$
- **Euler Variance Contribution of Factor $k$:**
  $$RC_k^{var} = \beta_{p,k} (\boldsymbol{\Sigma}_F \boldsymbol{\beta}_p)_k$$
  $$\sum_{k=1}^K RC_k^{var} = \sigma_{sys}^2$$
- **Systematic Portfolio Volatility:**
  $$\sigma_{sys} = \sqrt{\sigma_{sys}^2}$$
- **Euler Volatility Contribution of Factor $k$:**
  $$RC_k^{vol} = \frac{\beta_{p,k} (\boldsymbol{\Sigma}_F \boldsymbol{\beta}_p)_k}{\sigma_{sys}} = \beta_{p,k} \cdot MRC_k^{vol}$$
  $$\sum_{k=1}^K RC_k^{vol} = \sigma_{sys}$$
- **Marginal Risk Contribution (MRC):**
  $$MRC_k^{vol} = \frac{\partial \sigma_{sys}}{\partial \beta_k} = \frac{(\boldsymbol{\Sigma}_F \boldsymbol{\beta}_p)_k}{\sigma_{sys}}$$

### 2.5 Total Modeled Portfolio Risk
When residual variance $\sigma_\epsilon^2$ is included:
$$\sigma_{total}^2 = \sigma_{sys}^2 + \sigma_\epsilon^2 + 2 \, \text{Cov}(\boldsymbol{\beta}_p^T \mathbf{F}, \boldsymbol{\epsilon})$$
$$\sigma_{total} = \sqrt{\sigma_{total}^2}$$

---

## 3. Database Schema Architecture

The module introduces 7 authoritative tables in SQLAlchemy 2.x:

1. `m08_04_attribution_configs`: Versioned attribution settings (model, excess/total return basis, linking method, covariance estimation, tolerances).
2. `m08_04_covariance_snapshots`: Factor covariance matrices ($\boldsymbol{\Sigma}_F$) cached with condition number, positive semidefiniteness validation, and deterministic content hashes.
3. `m08_04_return_attribution_runs`: Header records for realized return attribution runs with Carino compound metrics.
4. `m08_04_return_attribution_components`: Detailed factor-level return contributions ($C_{k,cum}$), weights, and marginal impacts.
5. `m08_04_risk_attribution_runs`: Header records for forward-looking and ex-post systematic factor risk runs.
6. `m08_04_risk_attribution_components`: Euler risk decomposition records ($RC^{var}, RC^{vol}, MRC^{vol}, \% \text{ contribution}$).
7. `m08_04_attribution_reconciliations`: Formal audit records validating return and risk balances against tolerance boundaries.

---

## 4. Integration Lineage

```
M08.01 Factor Definition ──► M08.02 Factor Exposure ──► M08.03 Factor Sensitivity
     │                              │                             │
     └──────────────────────────────┼─────────────────────────────┘
                                    ▼
                         M08.04 Factor Attribution
                        ├── Factor Return Attribution (Carino)
                        ├── Factor Risk Attribution (Euler)
                        └── Audit Reconciliation Bridge
```
