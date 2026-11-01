# M04.05 Price Reference REST API Reference

All endpoints are mounted under `/api/v1/price-references`.

---

## 1. Register Reference Price Observation
**`POST /api/v1/price-references/observations`**

### Request Body (Official Close Example)
```json
{
  "price_reference_id": "OBS_AAPL_2026_09_01",
  "instrument_id": "INST_AAPL_001",
  "exchange_code": "NASDAQ",
  "trading_date": "2026-09-01",
  "reference_type": "OFFICIAL_CLOSE",
  "price_value": "225.500000",
  "currency": "USD",
  "price_basis": "RAW",
  "currency_basis": "NATIVE_CURRENCY",
  "price_origin": "EXCHANGE_OFFICIAL"
}
```

### Response (`201 Created`)
```json
{
  "price_reference_id": "OBS_AAPL_2026_09_01",
  "instrument_id": "INST_AAPL_001",
  "listing_id": null,
  "exchange_code": "NASDAQ",
  "market_segment": "EQUITY_CASH",
  "trading_date": "2026-09-01",
  "reference_type": "OFFICIAL_CLOSE",
  "price_value": "225.500000",
  "currency": "USD",
  "quotation_unit": "PER_SHARE",
  "price_basis": "RAW",
  "currency_basis": "NATIVE_CURRENCY",
  "price_origin": "EXCHANGE_OFFICIAL",
  "source_name": "EXCHANGE_FEED",
  "verification_status": "VERIFIED",
  "observation_version": 1,
  "created_at": "2026-11-01T07:50:00.000000"
}
```

---

## 2. Resolve Session-Aware Previous Close
**`POST /api/v1/price-references/previous-close/resolve`**

Uses the M04.04 Trading Calendar to find the prior eligible trading session and return its verified official close.

### Request Body
```json
{
  "instrument_id": "INST_AAPL_001",
  "exchange_code": "NASDAQ",
  "target_trading_date": "2026-09-02"
}
```

### Response (`200 OK`)
```json
{
  "resolution_id": "PCR_A1B2C3D4E5F6",
  "instrument_id": "INST_AAPL_001",
  "listing_id": null,
  "exchange_code": "NASDAQ",
  "target_trading_date": "2026-09-02",
  "previous_trading_date": "2026-09-01",
  "source_price_reference_id": "OBS_AAPL_2026_09_01",
  "resolved_price_value": "225.500000",
  "currency": "USD",
  "price_basis": "RAW",
  "resolution_status": "RESOLVED",
  "selection_policy": "OFFICIAL_EXCHANGE_CLOSE_PREFERRED",
  "resolved_at": "2026-11-01T07:50:01.000000"
}
```

---

## 3. Register Currency Conversion
**`POST /api/v1/price-references/currency-conversions/register`**

### Request Body
```json
{
  "converted_price_reference_id": "OBS_AAPL_2026_09_01_INR",
  "original_price_reference_id": "OBS_AAPL_2026_09_01",
  "target_currency": "INR",
  "fx_rate": "83.50000000",
  "fx_pair": "USD/INR",
  "conversion_direction": "SOURCE_TO_TARGET",
  "fx_source": "RBI_REFERENCE_RATE"
}
```

### Response (`201 Created`)
```json
{
  "converted_price_reference_id": "OBS_AAPL_2026_09_01_INR",
  "original_price_reference_id": "OBS_AAPL_2026_09_01",
  "source_currency": "USD",
  "target_currency": "INR",
  "fx_rate": "83.50000000",
  "fx_pair": "USD/INR",
  "conversion_direction": "SOURCE_TO_TARGET",
  "conversion_timestamp": "2026-11-01T07:50:02.000000",
  "converted_price_value": null
}
```

---

## 4. Retrieve Price References for an Instrument
**`GET /api/v1/price-references/instrument/{instrument_id}?limit=100&offset=0`**

Retrieves chronologically ordered observations for an instrument.

