# M09.05 — Slippage Estimation Architecture

## 1. Executive Overview

**M09.05 Slippage Estimation** is an institutional execution-quality analytics engine within the **Institutional Portfolio Risk Dashboard**. It quantifies the difference between intended benchmark prices and executed transaction prices across single orders and parent orders.

### Core Mathematical Formulations

1. **Benchmark Definition**:
   - Arrival Midpoint:
     $$M_{\text{arrival}} = \frac{B + A}{2}$$
   - Decision Price $P_{\text{decision}}$, Arrival Price $P_{\text{arrival}}$, Best Bid/Ask, or custom user reference.

2. **Execution Price (VWAP)**:
   $$VWAP_{\text{exec}} = \frac{\sum_{j=1}^k P_j Q_j}{\sum_{j=1}^k Q_j}$$

3. **Signed Realized Slippage** ($S = +1$ for BUY, $-1$ for SELL):
   $$\text{Slip}_{\text{price}} = S \cdot (VWAP_{\text{exec}} - P_{\text{ref}})$$
   $$\text{Slip}_{\text{bps}} = S \cdot \frac{VWAP_{\text{exec}} - P_{\text{ref}}}{P_{\text{ref}}} \times 10,000$$
   $$\text{Slip}_{\text{money}} = S \cdot (VWAP_{\text{exec}} - P_{\text{ref}}) \cdot Q_{\text{filled}} \cdot M$$

4. **Exact Additive Attribution Decomposition**:
   $$\text{Total Price Deviation} \equiv \text{Market Movement} + \text{Spread Crossing} + \text{Residual Execution}$$
   - **Market Movement**:
     $$\text{MarketMove}_j = S \cdot (M_j - P_{\text{ref}})$$
   - **Spread Crossing**:
     $$\text{SpreadComponent}_j = (A_j - M_j) \text{ [BUY]}, \quad (M_j - B_j) \text{ [SELL]}$$
   - **Residual Execution Concession**:
     $$\text{ResidualExecution}_j = S \cdot (P_j - M_j) - \text{SpreadComponent}_j$$
   *Note: Passive fills and price improvement yield negative residual concessions, correctly recorded without clamping.*

5. **Opportunity Cost & Implementation Shortfall**:
   $$\text{OpportunityCost} = S \cdot (P_{\text{terminal}} - P_{\text{ref}}) \cdot Q_{\text{unfilled}} \cdot M$$
   $$\text{ImplementationShortfall} = \text{Slip}_{\text{money}} + \text{OpportunityCost} + \text{Fees}_{\text{total}}$$

6. **Model Calibration Tracking**:
   $$\text{Mean Error (Bias)} = \frac{1}{N}\sum (\hat{S}_i - S_i)$$
   $$\text{MAE} = \frac{1}{N}\sum |\hat{S}_i - S_i|$$
   $$\text{RMSE} = \sqrt{\frac{1}{N}\sum (\hat{S}_i - S_i)^2}$$
   $$\text{Coverage Rate} = \frac{1}{N}\sum \mathbb{I}(L_i \le S_i \le U_i)$$

---

## 2. Component Structure

- `calculations/slippage_math.py`: Pure high-precision mathematical engine using `Decimal` arithmetic.
- `models/slippage_models.py`: SQLAlchemy 2.x ORM models supporting benchmark configuration, execution summaries, fill attributions, opportunity cost, and calibration runs.
- `schemas/slippage_schemas.py`: Pydantic v2 schemas with input validation.
- `repositories/slippage_repository.py`: Async database access patterns.
- `services/slippage_service.py`: Orchestration service handling calculations and persistence.
- `router.py`: REST endpoints mounted under `/api/v1/market-microstructure/slippage`.

