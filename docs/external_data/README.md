# External data integrations — free-only

The `/api/v1/external-data` gateway fetches provider-native data. It does **not**
automatically mark data fresh, populate portfolio valuations, or certify risk outputs.
Every successful result includes provider, operation, retrieval time, `RAW_UNVALIDATED`
quality and a reminder to check the provider's observation timestamps. Missing inputs,
credentials, empty results, rate limits and unexpected response schemas fail explicitly.

## Availability

| Provider | Implemented access | Activation |
|---|---|---|
| Alpha Vantage | Quote, compact daily history, company overview and statements | Existing key; endpoint/symbol eligibility depends on free entitlement |
| SEC EDGAR | Company submissions and company facts (XBRL) | SEC_USER_AGENT with contact email; no API key |
| FRED | Series observations, date filters and pagination | Free FRED_API_KEY |
| Financial Modeling Prep | Profile, income/balance/cash-flow statements and ratios | Free FMP_API_KEY; some datasets may be denied on the free plan |
| Upstox (chosen instead of Kite) | Quotes, holdings, positions, order-book reads | UPSTOX_ACCESS_TOKEN from the user's broker OAuth login |
| Upstox News | Instrument, holdings and positions news | Same token; entitlement determined by provider |
| NSE Data & Analytics | Catalog entry only, explicitly blocked | Licensed feed not enabled under the free-only requirement |
| BSE Market Data | Catalog entry only, explicitly blocked | Licensed feed not enabled under the free-only requirement |
| Databento | Catalog entry only, explicitly blocked | Metered service not enabled, including trial-credit consumption |
| RBI DBIE | Catalog entry only, explicitly blocked | No verified public API contract; official exports can be used in a future import adapter |

There is no order placement, OAuth token exchange UI, WebSocket ingestion or automatic
valuation integration in this gateway. These require additional provider-specific work.
No accounts or subscriptions were created. No paid requests were made.

## Configuration

Set server-side variables in `.env`; blank examples are in `.env.example`:

```
SEC_USER_AGENT="PortfolioRiskDashboard YourContactEmail"
FRED_API_KEY=
FMP_API_KEY=
UPSTOX_ACCESS_TOKEN=
```

Restart the backend after changing environment settings. Never put external credentials
in the browser, request parameters, source files, screenshots or Git. The UI's Data
Providers tab takes the **internal dashboard key**, stored only in component memory.

## HTTP interface

`GET /api/v1/external-data/providers` requires the internal read-only key or higher.
`POST /api/v1/external-data/{provider}/{operation}` requires operator or admin access.
Both use `X-API-Key`. Responses never include configured credential values.

Example bodies (send to the corresponding operation):

```json
{"parameters":{"cik":"320193"}}
```

Use with `sec_edgar/submissions` or `sec_edgar/company_facts`.

```json
{"parameters":{"series_id":"DGS10","observation_start":"2026-01-01","limit":100}}
```

Use with `fred/observations`. Missing FRED observations remain `.` rather than zero.

```json
{"parameters":{"symbol":"IBM"}}
```

Use with `alpha_vantage/quote`, `alpha_vantage/daily`, or `fmp/income_statement`.

```json
{"parameters":{"instrument_key":"NSE_EQ|INE002A01018"}}
```

Use with `upstox/quotes`. Holdings/positions/orders take `{"parameters":{}}`.

```json
{"parameters":{"category":"instrument_keys","instrument_keys":"NSE_EQ|INE002A01018","page_size":20}}
```

Use with `upstox_news/news`. Categories `holdings` and `positions` need no instrument list.

Outbound destinations and operations are allowlisted; arbitrary URLs and credential
overrides are rejected. Redirects are disabled. Responses are bounded at 10 MB, requests
time out after 20 seconds and are paced to at most four per second per process. There
are no automatic retries. Alpha Vantage shares the existing local quota scheduler.
For multiple workers deploy a shared limiter; local pacing is not a distributed quota.
Upstox token expiry must be handled by the account owner refreshing the token.

## Verification

```
python -m pytest backend/tests/modules/external_data -q
```

Tests use mock HTTP transport (no provider charges). They cover official request paths,
authentication, error payloads, rate limits, missing configuration, parameter injection,
source labels, credential redaction and rejection of silent simulator fallbacks.

## Official references

- SEC: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC access policy: https://www.sec.gov/about/developer-resources
- FRED: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- FMP: https://site.financialmodelingprep.com/developer/docs/stable/income-statement
- Upstox quotes: https://upstox.com/developer/api-documentation/get-full-market-quote/
- Upstox news: https://upstox.com/developer/api-documentation/get-news/
- NSE: https://www.nse.in/static/market-data/real-time-data-subscription
- BSE: https://marketdata.bseindia.com/
- Databento: https://databento.com/docs/api-historical/timeseries/timeseries-get-range
- RBI: https://data.rbi.org.in/
