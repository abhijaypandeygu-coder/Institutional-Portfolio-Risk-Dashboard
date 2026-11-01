# Module 03.02: Price Validation — Architecture Specification

## 1. Overview & Objectives

The **M03.02 Price Validation** engine provides institutional-grade market data validation across Indian (`NSE`, `BSE`) and US (`NYSE`, `NASDAQ`) equities. 

Downstream quantitative risk models—including Value at Risk (VaR), Expected Shortfall (ES), Factor Risk Analytics, and Execution Liquidity models—are vulnerable to dirty or corrupt prices. A single non-numeric string, negative price, or split-induced price discontinuity can miscalculate portfolio risk or trigger unintended liquidations.

M03.02 enforces a 4-stage validation pipeline with full evidence preservation:
1. **M03.02.01 — Invalid Prices:** Nulls, non-numeric strings, non-finite values (NaN, Inf), negative prices, min/max range boundaries, tick-size divisibility, precision limits, and OHLC structural invariants.
2. **M03.02.02 — Zero Prices:** Field-specific zero policies (trade LTP zero rejected, quote side empty warning, provider sentinel quarantined, zero volume preserved).
3. **M03.02.03 — Extreme Movements:** Absolute & percentage jump thresholds, exchange price circuit limits (NSE/BSE upper/lower bands, US LULD), and corporate action continuity reviews (splits, bonuses).
4. **M03.02.04 — Reference Comparisons:** Prior valid close comparisons, official exchange reference values, cross-provider discrepancy calculations between independent sources (e.g. Primary Exchange vs Alpha Vantage), and currency compatibility checks.

---

## 2. Validation Flow Pipeline

```
Raw / Normalized Market Observation (Tick, OHLCV, Trade)
                │
                ▼
 Stage 1: Structural Price Validation
    - Non-numeric / NaN / Inf rejection
    - Negative equity price rejection
    - Range, tick size, and decimal precision checks
    - OHLC structural invariants
                │
                ▼
 Stage 2: Zero Price Validation
    - Executable trade at zero -> REJECTED
    - Quote bid/ask at zero -> ACCEPTED_WITH_WARNING (Empty queue)
    - Alpha Vantage sentinel zero -> QUARANTINED
    - Zero volume -> ACCEPTED (Not a price violation)
                │
                ▼
 Stage 3: Extreme Price Movement & Exchange Bands
    - Percentage & absolute movement thresholds
    - Official exchange price bands (upper/lower circuit bands)
    - Corporate action adjustment awareness
                │
                ▼
 Stage 4: Reference Price Comparison
    - Previous close comparison
    - Independent provider cross-comparison (|Price A - Price B| / Denom)
    - Currency compatibility verification
                │
                ▼
 Aggregate Decision & Downstream Eligibility
    - Status: ACCEPTED, ACCEPTED_WITH_WARNING, QUARANTINED, REJECTED, UNKNOWN
    - Downstream Eligibility: True only for ACCEPTED or ACCEPTED_WITH_WARNING
    - Idempotent Anomaly Incident Upsert & Evidence Item Persistence
```

---

## 3. Directory Layout

```
backend/app/modules/market_data_quality/price_validation/
├── framework/
│   └── math_utils.py            # High-precision Decimal utilities (tick check, discrepancies)
├── integrations/
│   └── m04_bridge.py            # Contract bridge to M04 Instrument & Reference Data
├── validators/
│   ├── structural_validator.py  # M03.02.01 Structural checks
│   └── zero_validator.py        # M03.02.02 Field-specific zero evaluation
├── movement/
│   └── movement_validator.py    # M03.02.03 Movement, exchange bands, corporate actions
├── reference/
│   └── reference_comparator.py  # M03.02.04 Previous close & cross-source comparisons
├── incidents/
│   └── repository.py            # Persistence layer for rules, results, evidence, and incidents
├── models.py                    # SQLAlchemy 2.x models
├── schemas.py                   # Pydantic 2.x request/response schemas
├── service.py                   # Central coordination service
└── router.py                    # FastAPI REST endpoints (/api/v1/quality/price-validation/*)
```
