# Architecture Specification: M05.06 Portfolio Reconciliation

## 1. Executive Summary
`M05.06 Portfolio Reconciliation` provides the institutional-grade comparison, discrepancy detection, and break investigation engine of the *Institutional Portfolio Risk Dashboard*. It ensures that external records from prime brokers, custodians, and fund administrators align with authoritative internal books across positions ([M05.02](file:///d:/HFTs/portfolio/backend/app/modules/portfolio_management/position_management)), cash balances ([M05.04](file:///d:/HFTs/portfolio/backend/app/modules/portfolio_management/cash_management)), and transactions ([M05.05](file:///d:/HFTs/portfolio/backend/app/modules/portfolio_management/transaction_management)).

---

## 2. Core Architectural Boundaries & Integrity
1. **Never Directly Modify Internal Books:**
   - M05.06 is strictly an analytical and reconciliation break management system.
   - It never overwrites internal positions, cash balances, or transaction ledgers directly.
   - When a discrepancy indicates an internal record is missing or incorrect, an auditable resolution request is handed off to the owning module (e.g. M05.02 for position adjustments, M05.04 for cash adjustments).
2. **Statement Normalization & Idempotency:**
   - External statements are hashed upon intake (`SHA-256`) to prevent duplicate ingestion.
   - Statement rows are normalized into provider-agnostic staging records linked to the original file source.
3. **Deterministic Difference Formulas:**
   - **Position Quantity Difference:**
     $$\Delta Q = Q_{\text{external}} - Q_{\text{internal}}$$
   - **Cash Balance Difference:**
     $$\Delta C = C_{\text{external}} - C_{\text{internal}}$$
4. **Complete Break Lifecycle:**
   - Breaks progress through: `DETECTED` $\to$ `OPEN` $\to$ `ASSIGNED` $\to$ `INVESTIGATING` $\to$ `PENDING_REVIEW` $\to$ `RESOLVED` / `CLOSED` / `REOPENED`.
   - Investigation notes and resolution root-cause classifications (`TIMING_DIFFERENCE`, `PENDING_SETTLEMENT`, etc.) are preserved in immutable audit tables.

