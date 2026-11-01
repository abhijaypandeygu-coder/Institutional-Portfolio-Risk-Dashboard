# M04.01 Instrument Master API Reference

All endpoints are hosted under `/api/v1/instruments`.

## 1. Canonical Instrument Endpoints

### Create Canonical Instrument
- **POST** `/api/v1/instruments/`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`
- **Body:**
```json
{
  "canonical_name": "Apple Inc.",
  "short_name": "Apple",
  "instrument_type": "COMMON_STOCK",
  "asset_class": "EQUITY",
  "issuer_name": "Apple Inc.",
  "isin": "US0378331005",
  "country_of_issue": "USA",
  "issue_currency": "USD",
  "primary_market_id": "NASDAQ"
}
```

### Search & List Instruments
- **GET** `/api/v1/instruments/?query=Apple&limit=50`
- **Headers:** `X-API-Key: readonly_dev_secret_key_2026`

### Resolve Identifier (M02 / M03 Entrypoint)
- **GET** `/api/v1/instruments/resolve?exchange=NASDAQ&symbol=AAPL`
- **Headers:** `X-API-Key: readonly_dev_secret_key_2026`
- **Response:**
```json
{
  "match_status": "EXACT_MATCH",
  "instrument_id": "INST_6BE274E58A66",
  "canonical_name": "Apple Inc.",
  "listing_id": "LST_943F7E9BC83C",
  "exchange_id": "NASDAQ",
  "exchange_symbol": "AAPL",
  "isin": "US0378331005",
  "confidence_score": 1.0
}
```

### Update Instrument Attributes
- **PATCH** `/api/v1/instruments/{instrument_id}`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`
- **Body:**
```json
{
  "canonical_name": "Apple Inc. Updated",
  "change_reason": "Official legal issuer re-registration"
}
```

---

## 2. Venue Listing Endpoints

### Create Venue Listing
- **POST** `/api/v1/instruments/{instrument_id}/listings`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`
- **Body:**
```json
{
  "market_id": "US",
  "exchange_id": "NASDAQ",
  "exchange_symbol": "AAPL",
  "trading_currency": "USD",
  "is_primary_listing": true
}
```

### Update Listing Lifecycle Status
- **POST** `/api/v1/instruments/listings/{listing_id}/status`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`
- **Body:**
```json
{
  "listing_status": "SUSPENDED",
  "change_reason": "Exchange trading halt pending regulatory review"
}
```

---

## 3. Staged Import Batch Endpoints

### Stage Batch Import
- **POST** `/api/v1/instruments/imports`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`
- **Body:**
```json
{
  "source_name": "NSE_SECURITY_MASTER_DAILY",
  "source_type": "CSV",
  "records": [
    {
      "canonical_name": "State Bank of India",
      "short_name": "SBIN",
      "isin": "INE062A01020",
      "exchange_id": "NSE",
      "exchange_symbol": "SBIN",
      "market_id": "IN"
    }
  ]
}
```

### Process Approved Import Batch
- **POST** `/api/v1/instruments/imports/{batch_reference}/process`
- **Headers:** `X-API-Key: admin_dev_secret_key_2026`

