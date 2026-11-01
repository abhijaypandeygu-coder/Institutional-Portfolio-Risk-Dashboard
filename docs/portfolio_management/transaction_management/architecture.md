# Architecture Specification: M05.05 Transaction Management

## 1. Executive Overview
`M05.05 Transaction Management` is the authoritative record of financial transaction and execution events within the portfolio management domain. It acts as an event capture and ledger ingestion layer, decoupling trade facts from downstream position quantities ([M05.02 Position Management](file:///d:/HFTs/portfolio/backend/app/modules/portfolio_management/position_management)) and cash accounting ([M05.04 Cash Management](file:///d:/HFTs/portfolio/backend/app/modules/portfolio_management/cash_management)).

---

## 2. Core Principles & Separation of Concerns
1. **Fact vs. Accounting Distinction:**
   - M05.05 records the transaction facts: individual execution fills, prices, quantities, timestamps, fees, transfers, and corrections.
   - M05.02 consumes position-effect events and derives signed position quantities.
   - M05.04 consumes cash-effect events and manages journals, reservations, and available cash.
2. **Multiple Executions Preserved:**
   - A single logical order or trade can have multiple fills.
   - Each fill is permanently preserved with its distinct timestamp, price, and quantity. Weighted average price is calculated as a derived metric, never overwriting original executions.
3. **Partial Cancellation Safety:**
   - Cancelling an order cancels only the unfilled remainder.
   - Completed execution fills remain economically valid and immutable.
4. **Controlled Manual Adjustments:**
   - Enforces separation of duties (the requesting trader cannot approve their own adjustment).
   - Approved adjustments publish compensating events to the appropriate destination module.
5. **Transactional Outbox Pattern:**
   - Ingestion of executions commits both the execution record and downstream outbox events atomically in the same database transaction.
