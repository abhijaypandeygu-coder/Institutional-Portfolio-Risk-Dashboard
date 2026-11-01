# M05.08 — Multi-Portfolio Management API Reference

All endpoints are mounted under `/api/v1/portfolio-groups`.

## 1. Portfolio Groups

### Create Group
- **URL:** `POST /api/v1/portfolio-groups`
- **Status:** `201 Created`
- **Request Body:**
```json
{
  "group_code": "GRP-US-EQUITY",
  "group_name": "US Equity Growth Strategy",
  "group_type": "STRATEGY",
  "owner_reference": "USR-QUANT-1",
  "reporting_currency": "USD",
  "primary_benchmark_reference": "SPX-TR",
  "shared_risk_convention": "RISK-CONV-99"
}
```

### Group Lifecycle Transitions
- `POST /api/v1/portfolio-groups/{group_id}/activate`
- `POST /api/v1/portfolio-groups/{group_id}/suspend`
- `POST /api/v1/portfolio-groups/{group_id}/close`
- `POST /api/v1/portfolio-groups/{group_id}/archive`

## 2. Membership Management

### Add Portfolio to Group
- **URL:** `POST /api/v1/portfolio-groups/{group_id}/members`
- **Status:** `201 Created`
- **Request Body:**
```json
{
  "portfolio_id": "PORT-001",
  "membership_role": "PRIMARY_MEMBER",
  "include_in_positions": true,
  "include_in_cash": true
}
```

### Remove Portfolio from Group (Effective-Dated)
- **URL:** `POST /api/v1/portfolio-groups/{group_id}/members/{portfolio_id}/remove`
- **Status:** `200 OK`

### Membership History Audit Trail
- **URL:** `GET /api/v1/portfolio-groups/{group_id}/membership-history`
- **Status:** `200 OK`

## 3. Shared Settings & Inheritance

### Resolve Effective Setting
- **URL:** `GET /api/v1/portfolio-groups/{group_id}/resolved-settings?setting_key=REPORTING_CURRENCY&portfolio_id=PORT-001`
- **Status:** `200 OK`
- **Description:** Returns resolved setting following hierarchy precedence: Portfolio Override -> Group Policy -> System Default.

## 4. Consolidation & Exposures

### Execute Consolidation Run
- **URL:** `POST /api/v1/portfolio-groups/{group_id}/consolidations/run`
- **Status:** `201 Created`
- **Request Body:**
```json
{
  "reporting_currency": "USD",
  "fx_rates_to_reporting": {
    "USD": "1.000000",
    "INR": "0.012000"
  }
}
```

### Get Group Exposure
- **URL:** `GET /api/v1/portfolio-groups/{group_id}/exposures`
- **Status:** `200 OK`
- **Description:** Returns gross/net market value, instrument net quantities, portfolio contribution breakdown, and analytical netting disclaimer.

### Compare Groups
- **URL:** `POST /api/v1/portfolio-groups/compare?group_id_1=GRP-1&group_id_2=GRP-2`
- **Status:** `200 OK`
- **Description:** Computes net exposure differences and analyzes overlapping vs distinct member portfolios.
