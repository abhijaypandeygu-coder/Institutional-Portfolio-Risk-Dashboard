# M06.07 Portfolio Allocation Architecture

## 1. Overview
The **Portfolio Allocation Engine (M06.07)** is an institutional-grade portfolio risk and accounting layer within the Institutional Portfolio Risk Dashboard. It calculates how portfolio capital is distributed across marked securities, cash balances, sectors, countries, and strategies using an explicitly declared NAV denominator. It reconciles balance-sheet components, computes normalized and gross weights, evaluates target allocation drift, and compares allocation changes against historical snapshots.

```mermaid
flowchart TD
    A[M05.02 Positions & M05.03 Valuations] --> B[M06.04 Instrument Exposure]
    C[M05.04 Authoritative Cash Management] --> D[M06.07 Portfolio Allocation Engine]
    B --> D
    E[M06.03 Sector & Industry Exposure] --> D
    F[M06.05 Geographic Exposure] --> D
    G[M05.08 Multi-Portfolio Consolidation] --> D
    
    D --> H[Capital Allocation & NAV Reconciliation]
    H -->|Net Securities + Cash NAV| I[Balance Sheet NAV]
    H -->|NAV - Components Sum| J[Reconciliation Residual]
    
    D --> K[Dual Percentage Weight Calculator]
    K --> K1[NAV Weight: Net MV / NAV]
    K --> K2[Normalized Weight: Long MV / Total Long]
    K --> K3[Gross Contribution: Gross MV / Total Gross]
    
    D --> L[Target Allocation Configuration & Drift]
    L --> M[Actual vs Target Drift pp & Alert Status]
    
    D --> N[Historical Snapshot Comparison M05.07]
```

## 2. Core Methodologies and Accounting Formulas

### 2.1 Balance Sheet NAV Decomposition
$$\text{NAV}_P = \text{Net Security Value} + \text{Cash NAV} + \text{Other NAV Components}$$
where:
$$\text{Net Security Value} = \sum_{i} L_i - \sum_{i} S_i$$
$$\text{Gross Security Exposure} = \sum_{i} L_i + \sum_{i} S_i$$

### 2.2 Dual Allocation Weights
- **NAV-Based Weight**:
  $$W_{i, \text{NAV}} = \frac{\text{Net MV}_i}{\text{NAV}_P}$$
  *(For short positions, retains signed negative weight $-S_i / \text{NAV}_P$)*
- **Normalized Invested Weight**:
  $$W_{i, \text{Invested}} = \frac{L_i}{\sum_j L_j}$$
- **Gross Exposure Weight**:
  $$W_{i, \text{Gross}} = \frac{G_i}{\sum_j G_j}$$
- **Cash NAV Weight**:
  $$W_{\text{Cash, NAV}} = \frac{\text{Cash NAV}}{\text{NAV}_P}$$

### 2.3 Allocation Drift
$$\text{Drift}_i^{pp} = \text{Actual Weight}_i - \text{Target Weight}_i$$
- Categorized as `WITHIN_TARGET`, `OVERWEIGHT`, `UNDERWEIGHT`, `MATERIAL_DRIFT`, or `UNPLANNED_ALLOCATION`.

## 3. Financial Precision & Integrity
- Computations use pure Python `Decimal` and PostgreSQL `NUMERIC(18, 6)` with `ROUND_HALF_UP`.
- Floating point arithmetic is prohibited.
- Integrates with M05.04 cash ledger without creating duplicate cash or valuation records.
