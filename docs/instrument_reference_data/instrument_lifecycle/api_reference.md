# M04.06 Instrument Lifecycle REST API Reference

All endpoints are mounted under `/api/v1/instrument-lifecycle`.

---

## 1. Register Listing Lifecycle
**`POST /api/v1/instrument-lifecycle/listings`**

### Request Body
```json
{
  "listing_id": "LIST_TCS_NSE",
  "instrument_id": "INST_TCS_001",
  "exchange_code": "NSE",
  "market_segment": "EQUITY_CASH",
  "first_trading_date": "2004-08-25",
  "initial_status": "ACTIVE"
}
```

### Response (`201 Created`)
```json
{
  "listing_id": "LIST_TCS_NSE",
  "instrument_id": "INST_TCS_001",
  "exchange_code": "NSE",
  "market_segment": "EQUITY_CASH",
  "first_listing_date": null,
  "first_trading_date": "2004-08-25",
  "last_trading_date": null,
  "effective_delisting_date": null,
  "current_status": "ACTIVE",
  "status_as_of": "2026-11-01T07:55:00.000000",
  "verification_status": "VERIFIED"
}
```

---

## 2. Register Suspension Event
**`POST /api/v1/instrument-lifecycle/suspensions`**

### Request Body
```json
{
  "suspension_id": "SUSP_TCS_2026_01",
  "listing_id": "LIST_TCS_NSE",
  "suspension_type": "REGULATORY_SUSPENSION",
  "effective_start_date": "2026-06-01",
  "is_open_ended": true,
  "reason": "Temporary investigation halt by exchange circular"
}
```

---

## 3. Register Resumption Event
**`POST /api/v1/instrument-lifecycle/resumptions`**

### Request Body
```json
{
  "resumption_id": "RESUMP_TCS_2026_01",
  "listing_id": "LIST_TCS_NSE",
  "related_suspension_id": "SUSP_TCS_2026_01",
  "resumption_type": "NORMAL_RESUMPTION",
  "effective_resume_date": "2026-06-15",
  "reason": "Investigation completed without adverse findings"
}
```

---

## 4. Register Delisting Event
**`POST /api/v1/instrument-lifecycle/delistings`**

### Request Body
```json
{
  "delisting_id": "DELIST_XYZ_2026",
  "listing_id": "LIST_XYZ_BSE",
  "delisting_type": "VOLUNTARY_DELISTING",
  "announcement_date": "2026-07-01",
  "last_trading_date": "2026-07-20",
  "effective_delisting_date": "2026-07-21",
  "reason": "Voluntary consolidation to NSE"
}
```

---

## 5. Historical Status as of Date
**`GET /api/v1/instrument-lifecycle/listings/{listing_id}/status/as-of?as_of_date=2026-06-10`**

### Response (`200 OK`)
```json
{
  "listing_id": "LIST_TCS_NSE",
  "as_of_date": "2026-06-10",
  "historical_status": "SUSPENDED"
}
```

---

## 6. Instrument-Level Lifecycle Summary
**`GET /api/v1/instrument-lifecycle/instruments/{instrument_id}/summary`**

Aggregates all venue listings to evaluate whether the corporate security is `ACTIVE`, `PARTIALLY_TRADABLE`, `SUSPENDED_ALL_LISTINGS`, or `RETIRED`.

