# Upstox account and market-data integration

## Dashboard surfaces

The **Upstox broker account** panel on the executive page displays positions,
long-term holdings, broker-reported P&L, signed-position gross exposure, margin fields,
market status and quotes for up to 20 distinct account instruments. Empty accounts
remain empty. Missing P&L stays unavailable rather than becoming a calculated estimate.

The **Upstox depth & spread** panel on Liquidity Analytics accepts official instrument
keys. It normalizes five bid/ask levels, LTP, previous-close movement, spread in basis
points, visible-book imbalance, source timestamps and depth changes. Missing sides,
stale quotes and crossed books are explicit. It uses the active WebSocket snapshot
when all requested keys are subscribed; otherwise it uses REST polling.

The **Upstox monitoring rules** panel on Risk Alerts evaluates price movement, wide
spread, depth deterioration, historical volatility, position gross exposure, position
P&L loss, market status, stale quotes and disconnected/stale streams. Thresholds are
editable. Background monitoring is explicitly started/stopped and evaluates every
30 seconds. Daily volatility is calculated for the first requested instrument, using
at least 20 daily log returns and sample standard deviation annualized by sqrt(252).
Missing inputs are returned separately; no triggered rule does not imply full coverage.

The **Upstox market inputs & price shocks** panel on Stress Testing retrieves daily
price/volume history and India VIX. It calculates parallel price-shock P&L for explicit
signed quantities, preserving short-position signs. It does not reprice options or
include FX, transaction costs or liquidity impact. Unadjusted daily candles may
contain corporate-action discontinuities; volatility is an input, not a forecast.

The **Upstox connection & subscriptions** panel on Data Feeds manages V3 WebSocket
subscriptions and shows actual state, last-message freshness, errors, token-expiry
metadata and operation diagnostics. It never exposes the broker token or authorized
socket URL. The provider registry starts unverified; successful calls mark providers
verified, and authentication failures remove that status. TLS verification is enabled.

## Running

Install `python -m pip install -r backend/requirements-upstox.txt` and restart the
backend so the new router is loaded. The frontend uses its existing `/api` proxy.
Enter the internal operator/admin key into each Upstox panel; it stays in memory.
External `UPSTOX_ACCESS_TOKEN` remains in server `.env`. Changes to it require a
backend restart. There is no OAuth login/refresh implementation here.

Five-level mode is the default. Thirty-level mode is implemented but rejected unless
`UPSTOX_ALLOW_30_LEVEL=true` is explicitly set by an entitled account owner. Do not
enable it under a free-only account without confirming entitlement. No paid plan or
subscription was purchased or enabled during implementation.

All new endpoints require operator or admin role. New paths are under
`/api/v1/broker/upstox`: GET `status`; POST `account`, `liquidity`, `risk`, `stress`,
`stream/start`, `stream/stop`, `monitor/start`, `monitor/stop`.
Queries use `instrument_keys` arrays, up to 20 unique keys. Stress accepts
`quantities`, `shock_pct`, `from_date`, `to_date`. Risk accepts the same dates and
`limits` object. The default history range is 120 days, capped at 366 days.

Example liquidity body:

```json
{"instrument_keys":["NSE_EQ|INE002A01018"]}
```

Example scenario body:

```json
{"instrument_keys":["NSE_EQ|INE002A01018"],"quantities":{"NSE_EQ|INE002A01018":10},"shock_pct":-10}
```

## Scope and deployment limits

Broker account data is labelled INR and is **not merged** into arbitrary local
portfolio IDs. These new broker panels consume real inputs independently of the
existing local portfolio and yfinance panels. No broker orders, product conversions,
payments or account changes are submitted by these integrations.

Monitoring rules, latest results, REST cache, subscriptions and diagnostics are
process-local, account-scoped state. Run one backend worker for these features;
multiple workers need a shared monitor/cache and a single subscription owner.
They do not create durable M11/M12 breach records or governance audit history.
Monitoring survives tab navigation but stops when explicitly stopped or the server
shuts down. Thirty-second monitoring is not tick-by-tick risk processing.

REST responses have a 15-second cache keyed by a token fingerprint. Stream tasks
have bounded subscriptions, message sizes and queues, and retry up to three times.
Changing subscriptions replaces the previous connection. Missing SDK/credentials
and provider denials produce explicit errors rather than simulated outputs.

## Verification performed

- Automated tests cover math, missing/stale inputs, fractional timestamps, V3 previous
  close, empty accounts, rejected tokens, short scenarios, authentication, parameter
  validation, entitlement gating and official protobuf decoding.
- Live read-only checks returned an empty broker account, five-level Reliance depth,
  75 daily candles for the explicit test range, and a decoded V3 WebSocket message.
- Browser checks verified account rendering, live ladder, historical volatility and
  price-shock results, configurable price alert, monitor stop, and stream connect/stop.
- No live trades were placed; 30-level entitlement was not tested.

## Official specifications

- https://upstox.com/developer/api-documentation/get-full-market-quote-v3/
- https://upstox.com/developer/api-documentation/get-user-fund-margin/
- https://upstox.com/developer/api-documentation/get-market-status/
- https://upstox.com/developer/api-documentation/get-market-data-feed-authorize-v3/
- https://upstox.com/developer/api-documentation/v3/get-market-data-feed/
- https://github.com/upstox/upstox-python
