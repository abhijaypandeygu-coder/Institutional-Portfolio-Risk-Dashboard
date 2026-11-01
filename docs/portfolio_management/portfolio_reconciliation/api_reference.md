# API Reference: M05.06 Portfolio Reconciliation

Base prefix: `/api/v1/reconciliation`

### Endpoints

#### 1. Providers
- `POST /providers`
  - Body: `ProviderCreate`
  - Registers an external financial record provider.
- `GET /providers`
  - Lists active external providers.

#### 2. Statements
- `POST /statements/import`
  - Body: `StatementImportCreate`
  - Imports, hashes, validates, and stages an external position, transaction, or cash statement.
- `GET /statements/{statement_id}`
  - Returns statement details and record counts.

#### 3. Reconciliation Runs
- `POST /runs`
  - Body: `ReconciliationRunCreate`
  - Triggers a reconciliation run comparing external statement data against M05.02/M05.04/M05.05 internal books.
- `GET /runs/{run_id}`
  - Retrieves run status, match statistics, and break counts.

#### 4. Break Management & Workflow
- `GET /breaks`
  - Query parameters: `portfolio_id`, `account_id`, `status`, `severity`.
- `GET /breaks/{break_id}`
  - Returns break details, differences, and attached investigation notes.
- `POST /breaks/{break_id}/assign`
  - Body: `BreakAssignRequest`
- `POST /breaks/{break_id}/notes`
  - Body: `BreakNoteCreate`
- `POST /breaks/{break_id}/resolve`
  - Body: `BreakResolveRequest`
- `POST /breaks/{break_id}/reopen`
  - Reopens a resolved/closed break upon receipt of revised evidence.

