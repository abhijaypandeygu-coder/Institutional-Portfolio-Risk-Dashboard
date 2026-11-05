# M10.02 — Hypothetical Scenarios Architecture

## 1. Executive Summary

The **M10.02 Hypothetical Scenarios** module provides an institutional-grade framework for formulating, validating, saving, executing, and analyzing user-defined hypothetical market stress scenarios. Unlike historical replay (M10.01), which applies realized historical market shocks, M10.02 allows risk managers, quantitative analysts, and portfolio managers to define forward-looking market shifts that may not exist in recorded financial history.

The architecture strictly delineates between three distinct impact channels:
1. **Channel A (Direct Valuation & Mark-to-Market PnL):** Immediate price and factor shocks that directly alter asset prices, revaluing positions and generating realized scenario PnL.
2. **Channel B (Risk-Model Assumption Shocks):** Volatility and correlation transformations that modify downstream covariance structures ($\Sigma_s = D_s R_s D_s$) and recalculate stressed parametric VaR and Expected Shortfall without altering asset prices or creating artificial PnL.
3. **Channel C (Liquidity Overlays):** Bid-ask spread widening, book depth depletion, and market volume contractions that model execution frictions and liquidation slippage without modifying underlying market order books.

---

## 2. Mathematical Framework & Shock Channels

### 2.1 Channel A: Valuation Shocks

#### Price Shock Formulations
Given baseline price $P_{i,0}$:
- **Percentage Shock:** $P_{i,s} = P_{i,0} \times (1 + \Delta\%)$
- **Absolute Shock:** $P_{i,s} = P_{i,0} + \Delta\$$
- **Target Price:** $P_{i,s} = P_{\text{target}}$

#### Factor Return Propagation
When direct price shocks are absent, factor shocks propagate into asset returns via multi-factor sensitivities:
$$R_{i,s} = \sum_{k=1}^K \beta_{i,k} \cdot \Delta F_k$$
$$P_{i,s} = P_{i,0} \times (1 + R_{i,s})$$

#### Position Revaluation & Portfolio PnL
For a position with signed quantity $q_i$ ($q_i > 0$ for long, $q_i < 0$ for short):
$$\text{MV}_{i,0} = q_i \times P_{i,0}$$
$$\text{MV}_{i,s} = q_i \times P_{i,s}$$
$$\text{PnL}_i = \text{MV}_{i,s} - \text{MV}_{i,0} = q_i \times (P_{i,s} - P_{i,0})$$
$$\text{Contribution}_i = \frac{\text{PnL}_i}{\text{NAV}_0}$$
$$\Delta \text{NAV} = \sum_{i=1}^N \text{PnL}_i, \quad R_{\text{portfolio}} = \frac{\Delta \text{NAV}}{\text{NAV}_0}$$

Reconciliation guarantee:
$$\sum_{i=1}^N \text{Contribution}_i \equiv R_{\text{portfolio}}$$

---

### 2.2 Channel B: Risk-Model Assumptions

#### Volatility Transformation
Given baseline volatility $\sigma_{i,0}$:
- **Percentage Shock:** $\sigma_{i,s} = \sigma_{i,0} \times (1 + \Delta\%)$
- **Absolute Shock:** $\sigma_{i,s} = \sigma_{i,0} + \Delta\$$
- **Target Volatility:** $\sigma_{i,s} = \sigma_{\text{target}}$

#### Correlation Matrix Validation & Higham-Style Spectral Repair
A valid correlation matrix $R$ must satisfy:
1. Symmetry: $R = R^T$
2. Unit diagonal: $R_{ii} = 1$
3. Boundary constraints: $-1 \le R_{ij} \le 1$
4. Positive Semidefinite (PSD): $\lambda_{\min}(R) \ge 0$

When analyst pairwise overrides or equicorrelation shocks violate PSD conditions ($\lambda_{\min} < 0$), the module executes Higham-style spectral projection:
1. Decompose symmetric matrix: $R = Q \Lambda Q^T$.
2. Clip eigenvalues: $\Lambda^* = \max(\Lambda, 10^{-8})$.
3. Reconstruct: $B = Q \Lambda^* Q^T$.
4. Re-normalize unit diagonal: $R^* = D_B^{-1/2} B D_B^{-1/2}$, where $D_B = \text{diag}(B)$.
5. Calculate Frobenius repair distance: $\|R^* - R\|_F$.

#### Stressed Covariance & Downstream Risk Metrics
$$\Sigma_s = D_s R_s D_s \quad \text{where } D_s = \text{diag}(\sigma_{1,s}, \dots, \sigma_{N,s})$$
$$\sigma_{p,s} = \sqrt{w^T \Sigma_s w}$$
$$\text{VaR}_{s, \alpha} = z_\alpha \cdot \sigma_{p,s} \cdot \text{NAV}_0$$
$$\text{ES}_{s, \alpha} = \left(\frac{\phi(z_\alpha)}{1 - \alpha}\right) \cdot \sigma_{p,s} \cdot \text{NAV}_0$$

---

### 2.3 Channel C: Liquidity Overlays

- **Stressed Bid-Ask Spread:** $S_{i,s} = S_{i,0} \times (1 + \Delta S\%)$
- **Stressed Depth:** $D_{i,s} = D_{i,0} \times (1 - \Delta D\%)$
- **Stressed Market Volume:** $V_{i,s} = V_{i,0} \times (1 - \Delta V\%)$
- **Estimated Liquidation Cost:**
  $$\text{Cost}_{\text{bps}} \approx \frac{S_{i,s}}{2 \cdot P_{i,0}} \times 10^4 + \gamma \cdot \left(\frac{|q_i|}{V_{i,s}}\right)^\alpha \times 10^4$$

---

## 3. Data Model Architecture

The database entities are structured under SQLAlchemy 2.x and SQLite/PostgreSQL:
1. `HypotheticalScenarioTemplate`: Reusable scenario definitions with owner, category, status (`DRAFT`, `ACTIVE`, `ARCHIVED`), and version tracking.
2. `HypotheticalScenarioTemplateVersion`: Immutable historical revisions of scenario templates.
3. `HypotheticalScenarioRun`: Execution instances recording scenario parameters, execution timestamps, portfolio NAV, total PnL, and status.
4. `HypotheticalScenarioPositionResult`: Granular instrument-level revaluation records.
5. `HypotheticalScenarioRiskResult`: Portfolio-level stressed volatility, VaR, and ES comparisons.
6. `HypotheticalScenarioLiquidityResult`: Position-level stressed liquidity and liquidation overlays.
7. `HypotheticalScenarioWarning`: Audit logs for non-fatal execution adjustments (e.g. PSD correlation repair).
8. `HypotheticalScenarioAuditLog`: Lifecycle change tracking for compliance and governance.

---

## 4. API Endpoints

- `POST /api/v1/scenarios/hypothetical/templates`: Create reusable scenario template.
- `GET /api/v1/scenarios/hypothetical/templates`: List scenario templates with optional filtering.
- `GET /api/v1/scenarios/hypothetical/templates/{template_id}`: Retrieve template details and shock parameters.
- `POST /api/v1/scenarios/hypothetical/runs`: Execute a hypothetical scenario run.
- `GET /api/v1/scenarios/hypothetical/runs/{run_id}`: Retrieve comprehensive run results (Valuation, Risk, Liquidity, Warnings).
