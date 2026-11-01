# API Reference: M05.04 Cash Management

Base path: `/api/v1/portfolios/{portfolio_id}/cash`

### Endpoints

#### 1. Cash Balances
- `GET /balances`
  - Returns current cash balance snapshots for all accounts and currencies in the portfolio.
- `GET /accounts/{account_id}/balances`
  - Returns cash balances for a specific account.

#### 2. Available Cash
- `GET /available?account_id=...&currency=USD`
  - Calculates and returns an explainable breakdown of available cash.

#### 3. Deposits & Withdrawals
- `POST /deposits`
  - Body: `DepositCreate`
  - Returns `CashMovementResponse`
- `POST /withdrawals`
  - Body: `WithdrawalCreate`
  - Returns `CashMovementResponse`

#### 4. Movements & Reservations
- `GET /movements`
  - Filters: `account_id`, `currency`, `movement_type`, `status`, `date_from`, `date_to`.
- `POST /reservations`
  - Body: `CashReservationCreate`
- `POST /reservations/{reservation_id}/release`
  - Body: `CashReservationRelease`
- `POST /reservations/{reservation_id}/adjust`
  - Body: `CashReservationAdjust`

#### 5. Transfers & Reconciliation
- `POST /transfers`
  - Body: `CashTransferCreate`
- `POST /reconciliation/run`
  - Body: `CashReconciliationRunCreate`

