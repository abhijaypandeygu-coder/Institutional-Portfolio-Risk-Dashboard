# Alpha Vantage Free Tier Integration Guide (M02 Addendum)

## 1. Overview
Alpha Vantage integration has been implemented strictly adhering to the **Free Plan** parameters for US and Indian Equities (BSE & NSE).

### Operational Constraints & Boundaries
1. **REST Polling Only**: Alpha Vantage Free does NOT offer WebSocket streaming. Streaming requests explicitly raise `UnsupportedCapabilityError`. Real-time L1/L2 order-book simulation runs independently via `SimulatedMarketDataAdapter`.
2. **Daily Call Budget & Safety Reserve**:
   - Provider Allowance: 25 calls/day.
   - Internal Daily Call Budget: 20 calls/day.
   - Reserved Safety Margin: 5 calls/day (prevents unexpected lockouts).
3. **Data Freshness Classification**:
   - `GLOBAL_QUOTE` & `TIME_SERIES_DAILY`: Marked explicitly as `END_OF_DAY` (never misrepresented as live intraday ticks).
   - Historical bars: Marked as `HISTORICAL`.
   - Simulator: Marked as `SIMULATED_REALTIME`.
4. **Excluded Premium Endpoints**:
   - `TIME_SERIES_INTRADAY`
   - `TIME_SERIES_DAILY_ADJUSTED`
   - `TIME_SERIES_DAILY` with `outputsize=full`
   - `REALTIME_BULK_QUOTES`
   - `REALTIME_BULK_BID_ASK_PRICES`
   Attempting to call these endpoints raises `UnsupportedCapabilityError`.

---

## 2. Supported Functions & Usages

| Function | Output & Purpose | Free Plan Constraints |
|---|---|---|
| `SYMBOL_SEARCH` | Equity ticker discovery (US & BSE/NSE). | Results cached in-memory to prevent repeated quota usage. |
| `TIME_SERIES_DAILY` | Compact daily OHLCV bars (open, high, low, close, volume). | `outputsize=compact` (maximum 100 observations, raw unadjusted). |
| `TIME_SERIES_WEEKLY` | Weekly OHLCV bars for macro horizon modeling. | On-demand retrieval, unadjusted. |
| `TIME_SERIES_MONTHLY` | Monthly OHLCV bars for multi-year horizon modeling. | On-demand retrieval, unadjusted. |
| `GLOBAL_QUOTE` | End-of-day summary quote (price, change, volume). | Cached within the same trading session. |

---

## 3. Environment Configuration

```env
ALPHA_VANTAGE_API_KEY=your_api_key_here
ALPHA_VANTAGE_BASE_URL=https://www.alphavantage.co/query
ALPHA_VANTAGE_PLAN=free
ALPHA_VANTAGE_DAILY_CALL_BUDGET=20
ALPHA_VANTAGE_ENABLED=true

MARKET_DATA_SIMULATOR_ENABLED=true
MARKET_DATA_DEFAULT_PROVIDER=alpha_vantage
```

> [!IMPORTANT]
> The API key is injected strictly at the adapter layer via environment configuration and is redacted (`***REDACTED***`) in all HTTP logging and application outputs.
