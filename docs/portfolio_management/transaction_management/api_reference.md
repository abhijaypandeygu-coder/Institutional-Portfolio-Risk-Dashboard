# API Reference: M05.05 Transaction Management

Base prefix: `/api/v1/portfolios/{portfolio_id}/transactions`

### Endpoints

#### 1. Transactions
- `POST /`
  - Body: `TransactionCreate`
  - Captures logical parent transaction/order.
- `GET /`
  - Query filters: `account_id`, `instrument_id`, `transaction_type`, `status`, `date_from`, `date_to`.
- `GET /{transaction_id}`
  - Returns detailed transaction record.

#### 2. Executions & Lifecycle
- `POST /{transaction_id}/executions`
  - Body: `TradeExecutionCreate`
  - Records an individual execution fill, updates average price, and publishes outbox events.
- `GET /{transaction_id}/executions`
  - Returns execution fills.
- `POST /{transaction_id}/cancel`
  - Cancels unexecuted remainder while preserving completed fills.
- `POST /{transaction_id}/corrections`
  - Body: `ExecutionCorrectionCreate`
  - Corrects an execution with full before/after audit lineage.
- `GET /{transaction_id}/lifecycle`
  - Returns audit trail of state transitions.
- `GET /{transaction_id}/delivery-status`
  - Returns downstream outbox delivery state.

#### 3. Transfers & Adjustments
- `POST /security-transfers`
  - Body: `SecurityTransferCreate`
  - Records security movement with linked debit/credit legs.
- `POST /adjustments`
  - Body: `AdjustmentCreate`
  - Submits manual adjustment request.
- `POST /adjustments/{adjustment_id}/approve`
  - Approves adjustment under separation of duties.
