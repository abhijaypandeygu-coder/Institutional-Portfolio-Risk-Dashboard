# M08.01 — Factor Definition: API Reference

## 1. Factor Registry Endpoints

### `GET /api/v1/factors`
Lists all equity factor definitions in the registry.
- **Query Parameters:**
  - `family` (optional): `MARKET`, `SIZE`, `VALUE`, `MOMENTUM`, `QUALITY`, `LOW_VOLATILITY`, `CUSTOM`
  - `market` (optional): `INDIA`, `UNITED_STATES`
  - `status` (optional): `DRAFT`, `PENDING_REVIEW`, `APPROVED`, `ACTIVE`, `DEPRECATED`, `REJECTED`
- **Response:** Array of `FactorDefinitionResponse`.

### `POST /api/v1/factors`
Registers a new factor identity along with its initial version ($v1$) and characteristics.
- **Request Body:** `CreateFactorDefinitionRequest`
- **Response:** `FactorDefinitionResponse` (Status 200 OK)

### `GET /api/v1/factors/{factor_id}`
Retrieves a specific factor definition and its latest active or approved version specification.
- **Path Parameters:**
  - `factor_id` (UUID): Target factor identifier.
- **Response:** `FactorDefinitionResponse`

### `POST /api/v1/factors/{factor_id}/versions`
Creates a new immutable version ($v+1$) for an existing factor upon methodology change.
- **Path Parameters:**
  - `factor_id` (UUID): Target factor identifier.
- **Request Body:** `CreateFactorVersionRequest` (mandates `change_rationale`)
- **Response:** `FactorDefinitionVersionResponse`

### `POST /api/v1/factors/seed`
Seeds canonical benchmark factor definitions (Market, Size, Value, Momentum, Quality) with pre-configured econometric specifications.
- **Query Parameters:**
  - `market`: `INDIA` or `UNITED_STATES` (default: `INDIA`)
- **Response:** Array of `FactorDefinitionResponse`

### `POST /api/v1/factors/versions/{version_id}/governance`
Executes risk-committee lifecycle governance transitions.
- **Path Parameters:**
  - `version_id` (UUID): Version to transition.
- **Request Body:**
  ```json
  {
    "action": "SUBMIT | APPROVE | ACTIVATE | REJECT | DEPRECATE",
    "actor": "RISK_COMMITTEE_CHAIR"
  }
  ```
- **Response:** `FactorDefinitionVersionResponse`

---

## 2. Factor Models API Endpoints

### `GET /api/v1/factor-models`
Lists all composite factor models (e.g., Fama-French 3-Factor, Carhart 4-Factor).
- **Response:** Array of `FactorModelResponse`.

### `POST /api/v1/factor-models`
Creates a multi-factor risk model version by composing exact pinned factor version IDs with deterministic ordering ($k=1, \dots, K$).
- **Request Body:**
  ```json
  {
    "model_code": "FF3_INDIA",
    "model_name": "Fama-French 3-Factor Model (India)",
    "description": "Standard 3-factor model for NSE/BSE equities: MKT, SMB, HML.",
    "market_scope": "INDIA",
    "currency_basis": "INR",
    "return_frequency": "DAILY",
    "factor_version_ids": [
      "version-uuid-mkt",
      "version-uuid-smb",
      "version-uuid-hml"
    ],
    "change_rationale": "Canonical 3-factor baseline"
  }
  ```
- **Response:** `FactorModelResponse`

### `GET /api/v1/factor-models/{model_id}`
Retrieves full factor model metadata, pinned factor memberships, positions, and SHA-256 model definition hash.
- **Path Parameters:**
  - `model_id` (UUID): Model identifier.
- **Response:** `FactorModelResponse`
