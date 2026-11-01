# M05.08 — Multi-Portfolio Management Architecture

## 1. Overview & System Context
The **M05.08 Multi-Portfolio Management** engine provides institutional logical grouping, cross-portfolio position aggregation, gross/net analytical exposure calculation, currency-isolated cash consolidation, and shared reference setting inheritance across independently maintained portfolios within the Institutional Portfolio Risk Dashboard.

```
       +-----------------------------------------------+
       |             Portfolio Group (M05.08)          |
       |  (Strategy / Desk / Mandate / Custom Group)   |
       +-----------------------------------------------+
              |                                  |
              v                                  v
+-----------------------------+    +-----------------------------+
|    Group Membership         |    |     Shared Policies         |
|  - Effective & Recorded Time|    |  - Reporting Currency       |
|  - Inclusion Toggles        |    |  - Benchmark References     |
|  - Deduplication Engine     |    |  - Risk Conventions         |
+-----------------------------+    +-----------------------------+
              |
              +--------------------+---------------------+
              |                    |                     |
              v                    v                     v
+-----------------------+ +--------------------+ +--------------------+
|   M05.02 Positions    | | M05.03 Valuations  | |   M05.04 Cash      |
| Authoritative Holdings| | Market Value & FX  | | Account Balances   |
+-----------------------+ +--------------------+ +--------------------+
              |                    |                     |
              +--------------------+---------------------+
                                   |
                                   v
             +-------------------------------------------+
             |         Consolidation Orchestrator        |
             | - Instrument Aggregation                  |
             | - Gross / Net Exposure Analytical Views   |
             | - Contributor Lineage Preservation        |
             | - Segregated Cash Summaries               |
             | - Immutable Group Snapshot & Hash         |
             +-------------------------------------------+
```

## 2. Key Architectural Guarantees

1. **Independent Ledger Preservation:**
   - M05.08 never alters the underlying position ledgers (M05.02), valuation records (M05.03), or cash subledgers (M05.04).
2. **Analytical Netting vs Legal Netting:**
   - Net positions are strictly analytical conveniences. They carry explicit disclaimers and do NOT imply legal settlement offsets or cross-portfolio collateral transferability.
3. **Lineage Traceability:**
   - Every consolidated holding preserves all contributing source portfolio and account line items via `PortfolioGroupHoldingContributor`.
4. **Deduplication:**
   - Portfolios belonging to multiple nested or overlapping groups are deduplicated before consolidation to prevent double-counting.
5. **Currency Segregation:**
   - Cash balances in different currencies are never added together directly. Reporting-currency conversions require explicit FX rates and preserve native currency figures.

