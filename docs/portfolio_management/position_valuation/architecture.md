# Architecture: M05.03 — Position Valuation

## 1. Executive Summary
**M05.03 — Position Valuation** is the authoritative valuation and cost-basis accounting engine of the Institutional Portfolio Risk Dashboard. It calculates the **market value**, **cost basis**, **unrealized P&L**, and **realized P&L** for open and closed equity holdings across Indian (NSE, BSE) and US (NYSE, NASDAQ) exchanges.

### Core Principles
1. **Signed Accounting Convention:**
   - Long positions have positive quantities ($Q > 0$), positive market values ($MV > 0$), and positive cost bases ($CB > 0$).
   - Short positions have negative quantities ($Q < 0$), negative market values ($MV < 0$), and negative cost bases (carrying proceeds basis, $CB < 0$).
   - **Unified Unrealized P&L Formula:**
     $$\text{Unrealized P\&L} = \text{Signed Market Value} - \text{Signed Cost Basis}$$
     - *Long Gain:* $MV = \$12,000, CB = \$10,000 \implies P\&L = +\$2,000$.
     - *Short Gain (Price drops):* $MV = -\$9,000, CB = -\$10,000 \implies P\&L = -\$9,000 - (-\$10,000) = +\$1,000$.
     - *Short Loss (Price rises):* $MV = -\$11,000, CB = -\$10,000 \implies P\&L = -\$11,000 - (-\$10,000) = -\$1,000$.
2. **Gross vs. Net Independence:**
   - Gross long market value and gross short market value are aggregated independently:
     $$MV_{\text{gross long}} = \sum \max(MV_i, 0), \quad MV_{\text{gross short}} = \sum \max(-MV_i, 0)$$
   - Net market value ($MV_{\text{net}} = MV_{\text{gross long}} - MV_{\text{gross short}}$) is a derived display metric that never obscures underlying exposures.
3. **Lot-Based Cost Basis & Realized P&L:**
   - Acquisition lots (`CostBasisLot`) maintain opening shares, unit price, consideration, and base-currency basis under FIFO or weighted average.
   - Partial sales allocate oldest lots via `CostBasisAllocation` records, generating auditable realized P&L without disturbing unallocated remaining lots.
4. **Multi-Currency & FX Lineage:**
   - Preserves native currency figures alongside portfolio base-currency conversions via explicitly versioned FX rates.

---

## 2. Component Diagram

```
                 Position Snapshot (M05.02) + Eligible Mark (M04.05)
                                          |
                                          v
                         +---------------------------------+
                         |   Position Valuation Service    |
                         | - Signed MV calculation         |
                         | - FX conversion to base curr    |
                         +---------------------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                                                   |
        v                                                                   v
+-------------------------------+                           +-------------------------------+
|     Open Holdings Path        |                           |     Closed Holdings Path      |
| - Retrieves active lots       |                           | - Allocates oldest FIFO lots  |
| - Calculates Unrealized P&L   |                           | - Calculates Realized P&L     |
| - Generates PositionValuation |                           | - Generates CostBasisAlloc    |
+-------------------------------+                           +-------------------------------+
        |                                                                   |
        +---------------------------------+---------------------------------+
                                          |
                                          v
                         +---------------------------------+
                         |  Portfolio Valuation Snapshot   |
                         | - Gross Long & Short Values     |
                         | - Net Market Value              |
                         | - Total Cost Basis & Unr P&L    |
                         +---------------------------------+
```

