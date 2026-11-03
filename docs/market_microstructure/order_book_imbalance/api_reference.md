# M09.08 Order Book Imbalance API Reference

## Base Path
`/api/v1/market-microstructure/order-book-imbalance`

---

### 1. Calculate & Persist Imbalance Snapshot
`POST /calculate`

Calculates best-level, multi-level, notional, weighted imbalance, and microprice from order book depth levels.

**Request Payload:**
```json
{
  "instrument_id": "INST-NVDA",
  "venue_id": "XNAS",
  "requested_levels": 3,
  "weighting_method": "EXPONENTIAL_LEVEL",
  "decay_parameter": 0.40,
  "levels": [
    {"level_index": 1, "bid_price": 120.00, "ask_price": 120.02, "bid_quantity": 2500, "ask_quantity": 1000},
    {"level_index": 2, "bid_price": 119.98, "ask_price": 120.04, "bid_quantity": 3000, "ask_quantity": 1500},
    {"level_index": 3, "bid_price": 119.96, "ask_price": 120.06, "bid_quantity": 4000, "ask_quantity": 2000}
  ]
}
```

**Response (201 Created):**
```json
{
  "snapshot_id": "IMB-A1B2C3D4E5F6",
  "instrument_id": "INST-NVDA",
  "venue_id": "XNAS",
  "event_timestamp": "2026-11-03T10:30:00Z",
  "best_level_imbalance": 0.4286,
  "multi_level_quantity_imbalance": 0.3571,
  "multi_level_notional_imbalance": 0.3569,
  "weighted_quantity_imbalance": 0.3852,
  "weighted_notional_imbalance": 0.3850,
  "bid_share": 0.6786,
  "ask_share": 0.3214,
  "total_bid_quantity": 9500.0,
  "total_ask_quantity": 4500.0,
  "total_bid_notional": 1139740.0,
  "total_ask_notional": 540190.0,
  "microprice": 120.0143,
  "midpoint": 120.0100,
  "microprice_deviation_bps": 3.58,
  "actual_level_count": 3,
  "regime": "MODERATE_BID",
  "quality_status": "ELIGIBLE",
  "config_id": "CFG-DEFAULT-IMBALANCE"
}
```

---

### 2. Get Latest Imbalance Snapshot
`GET /{instrument_id}/current?venue_id=XNAS`

Retrieves the latest calculated imbalance state for an instrument.

---

### 3. Analyze Persistence & Run Durations
`POST /persistence`

Analyzes state persistence (BID_DOMINANT, ASK_DOMINANT, NEUTRAL) and run durations across a time-series observation sequence.

**Request Payload:**
```json
{
  "instrument_id": "INST-NVDA",
  "venue_id": "XNAS",
  "threshold": 0.20,
  "observations": [
    {"timestamp": "2026-11-03T10:00:00Z", "imbalance": 0.35, "duration_seconds": 5.0},
    {"timestamp": "2026-11-03T10:00:05Z", "imbalance": 0.40, "duration_seconds": 5.0}
  ]
}
```

---

### 4. Detect Imbalance Reversals with Hysteresis
`POST /reversals`

Detects transitions across dominance states using hysteresis thresholds (`entry_threshold`, `exit_threshold`).

---

### 5. Multi-Venue Imbalance Comparison
`POST /venues`

Compares order book imbalance metrics across multiple venues (e.g. XNYS vs XNAS).

