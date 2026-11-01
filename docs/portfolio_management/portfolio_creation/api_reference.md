# API Reference: M05.01 — Portfolio Creation

## Base Path: `/api/v1/portfolios`

### 1. Portfolio Registration & Metadata
- **POST** `/`
  - Register new portfolio in `DRAFT` status with stable `portfolio_id` and unique `portfolio_code`.
- **GET** `/`
  - Query and filter portfolios by `lifecycle_status`, `base_currency`, or `portfolio_type`.
- **GET** `/{portfolio_id}`
  - Retrieve detailed portfolio record.
- **PATCH** `/{portfolio_id}`
  - Update mutable metadata (`portfolio_name`, `short_name`, `description`).
- **POST** `/{portfolio_id}/change-base-currency`
  - Controlled base currency change with required effective date, reason, and FX policy reference. Creates new configuration snapshot.

### 2. Strategy & Mandate Management
- **GET** `/strategies` & **POST** `/strategies`
  - Retrieve and define investment strategies in the global catalog.
- **POST** `/{portfolio_id}/strategies` & **GET** `/{portfolio_id}/strategies`
  - Assign strategy to portfolio with primary/secondary designation.
- **GET** `/mandates` & **POST** `/mandates`
  - Retrieve and register investment mandates.
- **POST** `/{portfolio_id}/mandates` & **GET** `/{portfolio_id}/mandates`
  - Assign investment mandate to portfolio.

### 3. Benchmarks & Ownership
- **POST** `/{portfolio_id}/benchmarks` & **GET** `/{portfolio_id}/benchmarks`
  - Associate primary, secondary, and composite benchmarks with custom weights.
- **POST** `/{portfolio_id}/ownership` & **GET** `/{portfolio_id}/ownership`
  - Assign managers, teams, desks, and legal entities with effective dates.

### 4. Hierarchy & Sleeves
- **POST** `/{portfolio_id}/hierarchy`
  - Link child portfolios, sleeves, or strategy groups with automated cycle detection.
- **GET** `/{portfolio_id}/children`
  - List direct child portfolios and sleeves.
- **GET** `/{portfolio_id}/ancestors`
  - List parent portfolio associations.

### 5. Valuation & Accounting Settings
- **POST** `/{portfolio_id}/valuation-settings` & **GET** `/{portfolio_id}/valuation-settings`
  - Configure valuation calendar, frequency, cutoff time, timezone, and price selection policy.
- **POST** `/{portfolio_id}/accounting-settings` & **GET** `/{portfolio_id}/accounting-settings`
  - Configure trade/settlement basis, cost-basis method (FIFO, weighted average), and dividend accrual.

### 6. Portfolio Limits
- **POST** `/{portfolio_id}/limits` & **GET** `/{portfolio_id}/limits`
  - Define exposure and leverage constraints with warning and hard thresholds.

### 7. Lifecycle State Machine
- **POST** `/{portfolio_id}/submit`: Move from `DRAFT` to `PENDING_APPROVAL`.
- **POST** `/{portfolio_id}/approve`: Move from `PENDING_APPROVAL` to `APPROVED`.
- **POST** `/{portfolio_id}/activate`: Move from `APPROVED` to `ACTIVE`.
- **POST** `/{portfolio_id}/suspend`: Move from `ACTIVE` to `SUSPENDED`.
- **POST** `/{portfolio_id}/resume`: Resume from `SUSPENDED` to `ACTIVE`.
- **POST** `/{portfolio_id}/close`: Transition to `CLOSED`.
- **GET** `/{portfolio_id}/lifecycle-history`: Query state transition audit log.

### 8. Configuration Reproducibility & Operational Metrics
- **GET** `/{portfolio_id}/configuration/as-of?as_of_date=YYYY-MM-DD`
  - Retrieve point-in-time configuration snapshot active on a specified historical date.
- **GET** `/metrics/operational`
  - Retrieve aggregated metrics: total, active, draft, suspended, closed, and breakdowns by currency, type, and market.
