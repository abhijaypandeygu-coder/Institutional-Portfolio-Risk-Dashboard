# M10.05 — Correlation Shock Module Architecture

## 1. Executive Summary

**Module ID:** M10.05  
**Module Name:** Correlation Shock  
**Parent Module:** M10 — Scenario Analysis & Stress Testing  
**Component Type:** Quantitative Risk & Stress Testing Engine  

The **Correlation Shock** module evaluates how simulated structural shifts, contagion, or breakdown in asset and factor co-movements affect total portfolio risk. The primary quantitative objective is to identify conditions under which portfolio diversification benefits weaken or entirely disappear under stressed market regimes.

---

## 2. Quantitative & Mathematical Framework

### 2.1 Pairwise Correlation Transformations
For an eligible pair of instruments or factors $(i, j)$ with baseline correlation $\rho_{ij}$, target correlation $\rho_{\text{target}}$, and stress intensity $\lambda \in [0, 1]$:

$$\rho_{ij}^{\text{stress}} = (1 - \lambda)\rho_{ij} + \lambda \rho_{\text{target}}$$

Specialized transformation modes supported:
1. **Increase:** Moves correlation toward a specified higher target level.
2. **Convergence:** Compresses correlations toward a common stress level (e.g., $0.80$, $0.85$, $0.90$).
3. **Convergence to One:** Models extreme diversification breakdown:
   $$\rho_{ij}^{\text{stress}} = (1 - \lambda)\rho_{ij} + \lambda$$
4. **Convergence to Zero:** Models decoupling or basis divergence:
   $$\rho_{ij}^{\text{stress}} = (1 - \lambda)\rho_{ij}$$
5. **Pairwise Overrides:** Direct pair-specific overrides preserving canonical entity ordering ($A \le B$).

### 2.2 Dedicated Matrix Validation Engine
The module strictly distinguishes mathematical positive semi-definiteness (PSD) from downstream model condition usability.
1. **Symmetry:** $|R - R^T| \le \epsilon$ (default $10^{-6}$).
2. **Unit Diagonal:** $R_{ii} \equiv 1.0$.
3. **Correlation Bounds:** $-1.0 \le R_{ij} \le 1.0$.
4. **PSD Eigenvalue Criterion:** All eigenvalues $\lambda_k \ge -\epsilon_{\text{psd}}$ (default $10^{-7}$).
5. **Rank and Condition Number:** Matrix rank $r = n$, condition number $\kappa = \frac{\lambda_{\max}}{\lambda_{\min}}$.

Explicit status states: `VALID`, `VALID_WITH_WARNINGS`, `INVALID_NON_SYMMETRIC`, `INVALID_DIAGONAL`, `INVALID_BOUNDS`, `INVALID_NON_PSD`, `SINGULAR`, `ILL_CONDITIONED`.

### 2.3 Controlled Matrix Repair Engine
Repair is never applied silently; every repair generates an immutable audit record:
1. **Eigenvalue Clipping:**
   $$R = Q \Lambda Q^T, \quad \lambda_i' = \max(\lambda_i, \delta)$$
   $$R' = Q \Lambda' Q^T, \quad D = \operatorname{diag}(R'), \quad R_{\text{repaired}} = D^{-1/2} R' D^{-1/2}$$
2. **Higham (2002) Alternating Projections:** Projection onto the closed convex cone of symmetric PSD matrices with unit diagonal.
3. **Shrinkage toward Identity:**
   $$R_{\text{shrunk}} = (1 - \alpha) R + \alpha I$$

### 2.4 Stressed Covariance & Recalculated Portfolio Risk
Given the repaired stressed correlation matrix $R^{\text{stress}}$ and volatility vector $\sigma$:
$$\Sigma^{\text{stress}} = D_\sigma R^{\text{stress}} D_\sigma$$
where $D_\sigma = \operatorname{diag}(\sigma_1, \dots, \sigma_n)$.

For signed portfolio weights $w$:
$$\sigma_p^{\text{stress}} = \sqrt{w^T \Sigma^{\text{stress}} w}, \quad \operatorname{Var}_p^{\text{stress}} = w^T \Sigma^{\text{stress}} w$$

### 2.5 Euler Risk Contribution Reconciliation
Decomposes portfolio risk with exact Euler additivity across both long and short positions:
1. **Marginal Risk Contribution (MRC):**
   $$\operatorname{MRC}_i = \frac{(\Sigma w)_i}{\sigma_p}$$
2. **Component Risk Contribution (CRC):**
   $$\operatorname{CRC}_i = w_i \operatorname{MRC}_i, \quad \sum_i \operatorname{CRC}_i \equiv \sigma_p$$
3. **Component Variance Contribution (CCV):**
   $$\operatorname{CCV}_i = w_i (\Sigma w)_i, \quad \sum_i \operatorname{CCV}_i \equiv \operatorname{Var}_p$$

### 2.6 Diversification Diagnostics
1. **Gross Standalone Volatility Comparison:**
   $$\operatorname{DB} = \sum_i |w_i| \sigma_i - \sigma_p$$
2. **Diversification Ratio (for non-negative weights):**
   $$\operatorname{DR} = \frac{\sum_i w_i \sigma_i}{\sigma_p}$$
3. **Pairwise Concentration:** Percentage of pairs exceeding thresholds ($>0.50$, $>0.70$, $>0.85$).

---

## 3. Database Schema Overview

The module introduces 10 normalized tables:
- `correlation_shock_scenarios`: Primary scenario registry and metadata.
- `correlation_shock_scenario_versions`: Immutable versioned configuration snapshots.
- `correlation_shock_scope_members`: Scope filters (instruments, sectors, groups, factors).
- `correlation_shock_pair_rules`: Canonical pair-specific correlation overrides.
- `correlation_shock_executions`: Execution lifecycle tracking with inlined baseline, raw stressed, and repaired matrices.
- `correlation_shock_matrix_diagnostics`: Eigendecomposition and validation at baseline, raw stressed, and repaired stages.
- `correlation_shock_repairs`: Audited repair transformations with Frobenius norm and max delta.
- `correlation_shock_risk_results`: Macro-level risk and diversification comparison metrics.
- `correlation_shock_risk_contributions`: Holding-level Euler risk contributions.
- `correlation_shock_audit_logs`: Detailed governance audit events.
