# M04.04 Trading Calendar REST API Reference

All endpoints are mounted under `/api/v1/trading-calendars`.

---

## 1. Register Exchange Calendar
**`POST /api/v1/trading-calendars`**

### Request Body (NSE Example)
```json
{
  "calendar_id": "CAL_NSE_EQ",
  "exchange_code": "NSE",
  "exchange_name": "National Stock Exchange of India",
  "market_country": "IND",
  "timezone_name": "Asia/Kolkata",
  "market_segment": "EQUITY_CASH",
  "effective_from": "2026-01-01"
}
```

---

## 2. Register Market Session Definition
**`POST /api/v1/trading-calendars/sessions`**

### Request Body
```json
{
  "session_id": "SESS_NSE_REGULAR",
  "calendar_id": "CAL_NSE_EQ",
  "session_code": "REGULAR",
  "session_name": "Continuous Trading",
  "session_type": "REGULAR_TRADING",
  "local_start_time": "09:15:00",
  "local_end_time": "15:30:00",
  "session_sequence": 2,
  "order_entry_permitted": true,
  "trade_matching_permitted": true,
  "data_capture_expected": true,
  "weekdays": "0,1,2,3,4"
}
```

---

## 3. Register Exchange Holiday
**`POST /api/v1/trading-calendars/holidays`**

### Request Body
```json
{
  "holiday_id": "HOL_NSE_2026_01_26",
  "calendar_id": "CAL_NSE_EQ",
  "holiday_date": "2026-01-26",
  "holiday_name": "Republic Day",
  "holiday_category": "NATIONAL_HOLIDAY",
  "trading_impact": "FULL_MARKET_CLOSURE",
  "source_reference": "NSE Circular 2026/01"
}
```

---

## 4. Register Calendar Exception
**`POST /api/v1/trading-calendars/exceptions`**

### Request Body (Early Close Example)
```json
{
  "exception_id": "EXC_NYSE_2026_11_27",
  "calendar_id": "CAL_NYSE_EQ",
  "exception_date": "2026-11-27",
  "exception_type": "EARLY_CLOSE",
  "affected_session_type": "REGULAR_TRADING",
  "replacement_end_time": "13:00:00",
  "trading_impact": "SESSION_MODIFICATION",
  "reason": "Day after Thanksgiving Early Close",
  "source_reference": "NYSE Holiday Schedule 2026"
}
```

---

## 5. Query Day Schedule
**`GET /api/v1/trading-calendars/lookup/day?exchange_code=NSE&target_date=2026-01-27`**

### Response (`200 OK`)
```json
{
  "exchange_code": "NSE",
  "calendar_id": "CAL_NSE_EQ",
  "trading_date": "2026-01-27",
  "classification": "REGULAR_TRADING_DAY",
  "is_trading_day": true,
  "timezone_name": "Asia/Kolkata",
  "holiday_name": null,
  "exceptions_applied": [],
  "sessions": [
    {
      "session_code": "REGULAR",
      "session_name": "Continuous Trading",
      "session_type": "REGULAR_TRADING",
      "local_start": "2026-01-27T09:15:00",
      "local_end": "2026-01-27T15:30:00",
      "utc_start": "2026-01-27T03:45:00Z",
      "utc_end": "2026-01-27T10:00:00Z",
      "utc_offset": "+05:30",
      "order_entry_permitted": true,
      "trade_matching_permitted": true,
      "data_capture_expected": true
    }
  ]
}
```

---

## 6. Resolve Session for Timestamp
**`GET /api/v1/trading-calendars/lookup/session?exchange_code=NYSE&query_time=2026-07-15T10:30:00`**

### Response (`200 OK`)
```json
{
  "exchange_code": "NYSE",
  "calendar_id": "CAL_NYSE_EQ",
  "resolved_trading_date": "2026-07-15",
  "local_datetime": "2026-07-15T10:30:00",
  "utc_datetime": "2026-07-15T14:30:00Z",
  "utc_offset": "-04:00",
  "is_trading_day": true,
  "session_classification": "REGULAR_TRADING",
  "scheduled_trading_permitted": true,
  "reason": null
}
```

---

## 7. Next / Previous Trading Day Lookups
- **`GET /api/v1/trading-calendars/lookup/next-trading-day?exchange_code=NSE&start_date=2026-05-01`**
- **`GET /api/v1/trading-calendars/lookup/previous-trading-day?exchange_code=NSE&start_date=2026-05-05`**

