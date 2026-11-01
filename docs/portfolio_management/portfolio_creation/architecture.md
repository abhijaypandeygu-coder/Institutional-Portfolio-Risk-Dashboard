# Architecture: M05.01 — Portfolio Creation

## 1. Executive Summary
**M05.01 — Portfolio Creation** provides the authoritative institutional registry, configuration engine, and identity manager for portfolios in the Institutional Portfolio Risk Dashboard. It establishes portfolio identity, classification, mandate constraints, multi-benchmark associations, multi-role ownership, hierarchical structures (parent portfolios, sleeves, strategy groups), valuation calendars, accounting conventions, and configurable limit definitions.

Crucially, **portfolio metadata is decoupled from portfolio holdings, transactions, and valuations**. M05.01 does not calculate NAVs, P&L, risk metrics, or monitor live limit breaches; it stores the authoritative configuration, parameters, and policies consumed by those downstream engines.

---

## 2. Core Architecture

```
                    Client / API / Ingestion
                               |
                               v
               +-------------------------------+
               |     Portfolio Master Registry |
               | - Stable UUID portfolio_id    |
               | - Unique portfolio_code       |
               | - Base currency (ISO-4217)    |
               | - Market & Asset Scope        |
               +-------------------------------+
                               |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
+---------------+      +---------------+      +---------------+
| Strategy &    |      | Benchmarks &  |      | Hierarchy &   |
| Mandate       |      | Ownership     |      | Sleeves       |
| - Primary/tag |      | - Primary/sec |      | - Tree DAG    |
| - Objective   |      | - Desk, Team  |      | - Cycle check |
| - Short/Lev   |      | - Effective   |      | - Pro-rata    |
+---------------+      +---------------+      +---------------+
        |                      |                      |
        +----------------------+----------------------+
                               |
                               v
               +-------------------------------+
               | Valuation & Accounting Policy |
               | - Trading calendar link       |
               | - Cutoff time & timezone      |
               | - Cost basis (FIFO/W-AVG)     |
               | - Dividend accrual rules      |
               +-------------------------------+
                               |
                               v
               +-------------------------------+
               | Limits & Reproducibility      |
               | - Category, scope, operator   |
               | - Warning & hard thresholds   |
               | - Point-in-time snapshots     |
               | - Immutable audit trail       |
               +-------------------------------+
```

---

## 3. Database Schema Entities

All entities are prefixed with `m05_` and managed via SQLAlchemy 2.x:
1. `m05_portfolios`: Primary registry holding identity, code, currency, lifecycle status, and active configuration version.
2. `m05_portfolio_strategies` & `m05_portfolio_strategy_assignments`: Multi-strategy tagging and classification.
3. `m05_portfolio_mandates` & `m05_portfolio_mandate_assignments`: Structured investment objectives, permissions (short selling, leverage), and constraints.
4. `m05_portfolio_benchmarks`: Primary, secondary, and composite benchmarks with configurable weights.
5. `m05_portfolio_ownerships`: Multi-entity ownership (users, teams, desks, legal entities) with historical validity dates.
6. `m05_portfolio_hierarchies`: Explicit parent-child, sleeve, and strategy-group relationships with automated cycle prevention.
7. `m05_portfolio_valuation_settings`: Portfolio reporting schedule, cutoff time, timezone, and price selection references.
8. `m05_portfolio_accounting_settings`: Trade vs. settlement date basis, cost-basis methodology (FIFO, weighted average), and dividend accrual treatment.
9. `m05_portfolio_limits`: Configuration of portfolio-level, sector-level, and asset-level limits and warning/hard thresholds.
10. `m05_portfolio_configuration_versions`: Immutable JSON snapshots for point-in-time audit and calculation reproducibility.
11. `m05_portfolio_lifecycle_events`: Audit trail for state transitions.
12. `m05_portfolio_audit_events`: Full compliance action logging.
